
from pydantic import BaseModel
from acex.configuration.components import ConfigComponent
from acex.configuration.components.interfaces import (
    # Interface,
    Loopback,
    # Physical,
    Svi
)
from acex.configuration.components.system import (
    HostName,
    Contact,
    Location,
    DomainName
)

from acex.configuration.components.system.ntp import NtpServer
from acex.configuration.components.system.ssh import SshServer
from acex.configuration.components.network_instances import NetworkInstance, L3Vrf
from acex.configuration.components.vlan import Vlan
from acex.models.attribute_value import AttributeValue

from acex.models import ExternalValue
from acex.models.composed_configuration import ComposedConfiguration
from collections import defaultdict
from typing import Dict
from string import Template
import json


class Configuration: 
    # Mapping from component type to path in composed configuration
    # Note that some paths are containers, like interfaces where the component also
    # must be referenced using its name attribute
    COMPONENT_MAPPING = {
        HostName: "system.config.hostname",
        Contact: "system.config.contact",
        Location: "system.config.location",
        DomainName: "system.config.domain_name",
        Loopback: "interfaces", 
        NetworkInstance: "network_instances",
        L3Vrf: "network_instances",
        Vlan: Template("network_instances.${network_instance}.vlans"),
        Svi: Template("network_instances.${network_instance}.interfaces")
    }

    # Some objects are also referenced in other parts.
    # For instance an interface belongs to configuration.interfaces, but 
    # are usually referenced in network_instances if tied to a VRF. 
    REFERENCE_MAPPING = {
        Svi: [Template("network_instances.${network_instance}.interfaces")],
        # Loopback: [Template("network_instances.${network_instance}.interfaces")]
    }
    
    # Reverse mapping from attribute name to path for __getattr__
    ATTRIBUTE_TO_PATH = {
        "hostname": "system.config.hostname",
        "contact": "system.config.contact",
        "location": "system.config.location",
        "domain_name": "system.config.domain_name",
    }
    
    def __init__(self, logical_node_id):
        self.composed = ComposedConfiguration()
        self.logical_node_id = logical_node_id

        # Komponenter lagras som objekt, mappade till sin position
        self._components = []


    # TODO: Den här är paj!
    def __getattr__(self, name: str):
        """
        Dynamically get configuration values by attribute name.
        Returns the actual value (not the AttributeValue wrapper).
        """
        # Avoid infinite recursion for internal attributes
        if name.startswith('_') or name in ('composed', 'logical_node_id'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
        # Check if this is a mapped attribute
        if name in self.ATTRIBUTE_TO_PATH:
            path = self.ATTRIBUTE_TO_PATH[name]
            try:
                attr_value = self._get_nested_component(path)
                # Check if it's an AttributeValue object
                if attr_value and hasattr(attr_value, 'get_value'):
                    return attr_value.get_value()
                # Fallback to dict format (for backwards compatibility)
                elif attr_value and isinstance(attr_value, dict):
                    return attr_value.get('value')
                return None
            except AttributeError:
                return None
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def _get_nested_component(self, path: str):
        """Get a nested attribute using dot notation path."""
        obj = self.composed
        parts = path.split('.')
        for part in parts:
            obj = getattr(obj, part)
        return obj

    def _set_attr_ptr_on_attributes(self, component):
        """
        Set attr_ptr metadata on each attribute of the component.
        Only necessary for externalValue types
        """
        # logical_nodes.0.ethernetCsmacd.if0.ipv4
        if component.name is not None:
            base_path = f"logical_nodes.{self.logical_node_id}.{component.type}.{component.name}"
        else:
            base_path = f"logical_nodes.{self.logical_node_id}.{component.type}"

        #TODO: If singleAttribute class, implementsmart logic to not use key 'value'

        for k, v in component.model.model_dump().items():
            attribute_value = getattr(component.model, k)
            if isinstance(attribute_value, AttributeValue):
                if attribute_value is not None and isinstance(attribute_value.value, ExternalValue):
                    attribute_value.metadata["attr_ptr"] = f"{base_path}.{k}"
            else:
                # print("Värde är inte attributeValue!")
                ...


    def _get_component_path(self, component) -> str:
        mapped_path = self.COMPONENT_MAPPING[type(component)]
        return self._render_path(component, mapped_path)

    def _get_reference_paths(self, component) -> list[str]:
        mapped_paths = self.REFERENCE_MAPPING.get(type(component), [])
        ref_points = []
        for ref_path in mapped_paths:
            ref_points.append(self._render_path(component, ref_path))
        return ref_points

    def _render_path(self, component, mapped_path: str):
        """
        The mapped path can either be a pure string, 
        or it can be a string.Template. If the latter, we need 
        to extract the variables and fetch corresponding values which 
        is expected to be attributeValues of the component itself.     
        """

        if isinstance(mapped_path, Template):
            vars_needed = [m.group('named') or m.group('braced')
               for m in mapped_path.pattern.finditer(mapped_path.template)
               if m.group('named') or m.group('braced')]

            value_map = {}
            for v in vars_needed:
                if hasattr(component.model, v):
                    av = getattr(component.model, v)
                    value_map[v] = av.value

            mapped_path = mapped_path.substitute(value_map)
        return mapped_path



    def add(self, component):
        """
        Add a configuration component to the composed configuration.
        Handles both dict-based and single-value components, sets external refs, and logs actions.
        Returns the added value or raises ValueError on error.
        """
        component_type = type(component)
        if component_type not in self.COMPONENT_MAPPING:
            print(f"Unknown component type: {component_type.__name__}")
            raise ValueError(f"Unknown component type: {component_type.__name__}")

        # ref is used to reference the absolute path of each attribute:
        self._set_attr_ptr_on_attributes(component)

        # modellen för composed talar om ifall vi behöver ett key för componenten:
        # Fix composite path for mapped objects. 
        composite_path = self._get_component_path(component)
        reference_points = self._get_reference_paths(component)

        if composite_path is not None:
            # lägger till komponenten i en flat list i en tuple med path.
            self._components.append((composite_path, component, reference_points))


    def as_model(self) -> BaseModel:

        # Dont edit the actual composed model, we make a model from a copy
        config = self.composed.copy()

        # Apply all values from components to the composed model: 
        for path, component, references in self._components:

            # Traverse the composed object to the ptr for the obj.
            path_parts = path.split('.')
            attribute_name = path_parts.pop()

            # First place the pointer on the attribute key
            ptr = config
            for part in path_parts:
                if isinstance(ptr, dict):
                    ptr = ptr.get(part)
                elif hasattr(ptr, part):
                    ptr = getattr(ptr, part)
                else:
                    raise Exception(f"Component pointer invalid for component: {component}, path: {path_parts}")


            # Get value of the pointer
            if isinstance(ptr, dict):
                value = ptr.get(attribute_name)
            else:
                value = getattr(ptr, attribute_name)
            
            # If the value of the ptr is a dict, the item has to be keyed
            if isinstance(value, dict):
                value[component.name] = component.model
            else:
                # Cant set value directly, since NoneType is a singleton.
                # Instead we use setattr using the pointer and attribute name.
                setattr(ptr, attribute_name, component.model)

            # Also add all references
            # print("lägg till referenspunkter här!")
            # for ref in references:
            #     print(ref)
            #     ref_ptr = config
            #     for part in ref.split('.'):
            #         print(f"part: {part}")
            #         if isinstance(ref_ptr, dict):
            #             ref_ptr = ref_ptr.get(part)
            #         else:
            #             ref_ptr = getattr(ref_ptr, part)
            #     # Set value: 
            #     if isinstance(ref_ptr, dict):
            #         ref_ptr[component.name] = component.model
            #     else:
            #         print("saknas sätt att montera in ref, på en annan component.")

        return config


    def to_json(self):
        """
        Serialisera alla komponenter till rätt position i strukturen.
        """
        return self.as_model().model_dump()

