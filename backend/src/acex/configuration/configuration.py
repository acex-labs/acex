
from pydantic import BaseModel
from acex.configuration.components import ConfigComponent
from acex.configuration.components.interfaces import (
    Loopback,
    Physical,
    Subinterface,
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
from acex.models.composed_configuration import ComposedConfiguration, Reference, RenderedReference
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
        Physical: "interfaces",
        Subinterface: "interfaces",
        NetworkInstance: "network_instances",
        L3Vrf: "network_instances",
        Vlan: Template("network_instances.${network_instance}.vlans"),
        # Svi: Template("network_instances.${network_instance}.interfaces")
        Svi: Template("interfaces")
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

        # Lagra alla Reference object. Läggs till efter att komponenter lagts till
        self._references = []

    
    def _get_nested_component(self, path: str):
        """Get a nested attribute using dot notation path."""
        obj = self.composed
        parts = path.split('.')
        for part in parts:
            obj = getattr(obj, part)
        return obj

    def _set_attr_ptr_on_attributes(self, component):
        """
        Set attr_ptr metadata on externalValue attributes of the component.
        # TODO: If singleAttribute class, implementsmart logic to not use key 'value'?
        """
        # example: logical_nodes.0.ethernetCsmacd.if0.ipv4
        if component.name is not None:
            base_path = f"logical_nodes.{self.logical_node_id}.{component.type}.{component.name}"
        else:
            base_path = f"logical_nodes.{self.logical_node_id}.{component.type}"

        for k, v in component.model.model_dump().items():
            attribute_value = getattr(component.model, k)
            if isinstance(attribute_value, AttributeValue):
                if attribute_value is not None and isinstance(attribute_value.value, ExternalValue):
                    attribute_value.metadata["attr_ptr"] = f"{base_path}.{k}"


    def _get_component_path(self, component) -> str:
        mapped_path = self.COMPONENT_MAPPING[type(component)]
        return self._render_path(component, mapped_path)

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

    def _pop_all_references(self, component):
        """
        Pops all references and stores them in a flat list instead.

        --> self._references
        """
        # Path is needed for this side of the edge
        mapped_path = self.COMPONENT_MAPPING[type(component)]
        rendered_mapped_path = self._render_path(component, mapped_path)

        if component.name is not None:
            self_path = f"{rendered_mapped_path}.{component.name}"
        else:
            self_path = rendered_mapped_path
        for k,v in component.kwargs.items():
            if isinstance(v, Reference):
                if v.direction == "to_self":
                    ri = RenderedReference(
                        from_ptr = v.pointer,
                        to_ptr = self_path
                    )
                else:
                    ri = RenderedReference(
                        from_ptr = self_path,
                        to_ptr = v.pointer
                    )
                self._references.append(ri)

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

        # pop references
        self._pop_all_references(component)

        # ref is used to reference the absolute path of each attribute:
        self._set_attr_ptr_on_attributes(component)

        # modellen för composed talar om ifall vi behöver ett key för componenten:
        # Fix composite path for mapped objects. 
        composite_path = self._get_component_path(component)

        if composite_path is not None:
            # lägger till komponenten i en flat list i en tuple med path.
            self._components.append((composite_path, component))

    def as_model(self) -> BaseModel:

        # Dont edit the actual composed model, we make a model from a copy
        config = self.composed.copy()

        # Apply all values from components to the composed model: 
        for path, component in self._components:

            # Set metadata of the component
            if hasattr(component.model, "metadata"):
                component.model.metadata.type = component.type

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


        # Add all references: 
        for reference in self._references:
            # Resolve destination value: 
            path_parts = reference.to_ptr.split('.')
            attr_name = path_parts.pop()
            ptr = config
            for part in path_parts:
                if isinstance(ptr, dict):
                    ptr = ptr.get(part)
                else:
                    ptr = getattr(ptr, part)

            # Get value of the pointer
            if isinstance(ptr, dict):
                destination_value = ptr.get(attr_name)
            else:
                destination_value = getattr(ptr, attr_name)
            # Resolve source value: 
            path_parts = reference.from_ptr.split('.')
            attr_name = path_parts.pop()
            ptr = config
            for part in path_parts:
                if isinstance(ptr, dict):
                    ptr = ptr.get(part)
                else:
                    ptr = getattr(ptr, part)

            # Get value of the pointer
            if isinstance(ptr, dict):
                source_item = ptr.get(attr_name)
            else:
                source_item = getattr(ptr, attr_name)

            if isinstance(source_item, dict):
                source_item[destination_value.name.value] = {
                    "name": destination_value.name.value,
                    "metadata": {
                        "type": "reference",
                        "ref_path": reference.to_ptr
                    }
                    }
        return config


    def to_json(self):
        """
        Serialisera alla komponenter till rätt position i strukturen.
        """
        return self.as_model().model_dump()

