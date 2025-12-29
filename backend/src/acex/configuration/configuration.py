
from pydantic import BaseModel
from acex.configuration.components import ConfigComponent
from acex.configuration.components.interfaces import (
    Loopback,
    #Physical,
    FrontpanelPort,
    LagInterface,
    ManagementPort,
    Subinterface,
    Svi
)
from acex.configuration.components.system import (
    HostName,
    Contact,
    Location,
    DomainName
)

from acex.configuration.components.system.logging import RemoteServer, Console, VtyLine, LoggingConfig, FileLogging
from acex.configuration.components.lacp import LacpConfig
from acex.configuration.components.system.ntp import NtpServer
from acex.configuration.components.system.ssh import SshServer, AuthorizedKey
from acex.configuration.components.network_instances import NetworkInstance, L3Vrf
from acex.configuration.components.vlan import Vlan
from acex.models.attribute_value import AttributeValue

from acex.models import ExternalValue
from acex.models.composed_configuration import ComposedConfiguration, Reference, ReferenceTo, ReferenceFrom, RenderedReference
from collections import defaultdict
from typing import Dict
from string import Template
import json


class Configuration: 
    # Mapping from component type to path in composed configuration
    # Note that some paths are containers, like interfaces where the component also
    # must be referenced using its name attribute
    COMPONENT_MAPPING = {
        AuthorizedKey: "system.ssh.host_keys",
        HostName: "system.config.hostname",
        Contact: "system.config.contact",
        Location: "system.config.location",
        DomainName: "system.config.domain_name",
        RemoteServer: "system.logging.remote_servers",
        Console: "system.logging.console",
        VtyLine: "system.logging.vty",
        LoggingConfig: "system.logging.config",
        FileLogging: "system.logging.files",
        LacpConfig: "lacp.config",
        #LacpInterfaces: "lacp.interfaces",
        #LacpConfgi: "lacp.config",
        Loopback: "interfaces", 
        #Physical: "interfaces",
        FrontpanelPort: "interfaces",
        LagInterface: "interfaces",
        ManagementPort: "interfaces",
        Subinterface: "interfaces",
        NetworkInstance: "network_instances",
        L3Vrf: "network_instances",
        Vlan: Template("network_instances.${network_instance}.vlans"),
        Svi: Template("interfaces"),
        NtpServer: "system.ntp.servers",
        SshServer: "system.ssh.config"
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
        Source of the reference must always be an attribute, destination 
        can be an object. 
        --> self._references
        """
        for k,v in component.kwargs.items():

            if isinstance(v, (ReferenceFrom, ReferenceTo)):
                self_component_path = self.COMPONENT_MAPPING[type(component)]
                rendered_self_component_path = self._render_path(component, self_component_path)

                # use key if item in dict
                if rendered_self_component_path.endswith('.config'):
                    self_path = f"{rendered_self_component_path}"
                else:    
                    self_path = f"{rendered_self_component_path}.{component.name}"

                if isinstance(v, ReferenceTo):
                    # if self is the source, the source must be an attribute. 
                    ri = RenderedReference(
                        from_ptr = f"{self_path}.{k}",
                        to_ptr = v.pointer
                    )
                elif isinstance(v, ReferenceFrom):
                    
                    ri = RenderedReference(
                        from_ptr = v.pointer,
                        to_ptr = f"{self_path}"
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

        # Add and resolve references:
        for reference in self._references:
            # From pointer is always an attribute, to is a referenced object

            # insertion point 
            insertion_path_parts = reference.from_ptr.split('.')
            insertion_attr = insertion_path_parts.pop()

            # referenced value
            value_path_parts = reference.to_ptr.split('.')
            value_attr = value_path_parts.pop()

            # pointer startpoint is the full config.
            ptr = config

            # Move pointer to the value
            for part in value_path_parts:
                if isinstance(ptr, dict):
                    ptr = ptr.get(part)
                else:
                    ptr = getattr(ptr, part)
            
            # Store pointer value, this will be inserted at insertion point
            pointer_value = ptr[value_attr]

            # Reset pointer to base of configuration
            ptr = config

            # Move pointer to insertion point
            for part in insertion_path_parts:
                if isinstance(ptr, dict):
                    ptr = ptr.get(part)
                else:
                    ptr = getattr(ptr, part)

            reference = Reference(
                pointer = reference.to_ptr
            )

            value = reference
            # Insert the referenced value dict to the insertion point.
            # If attribute of insertionpoint is a dict, value has to be keyed
            if isinstance(getattr(ptr, insertion_attr), dict):
                insertion_point = getattr(ptr, insertion_attr)
                insertion_point[pointer_value.name.value] = value
            else:
            # Otherwise, just set the source key as insertion point:
                setattr(ptr, insertion_attr, value)

        return config


    def to_json(self):
        """
        Serialisera alla komponenter till rätt position i strukturen.
        """
        return self.as_model().model_dump()

