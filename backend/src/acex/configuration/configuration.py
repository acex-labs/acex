
from acex.configuration.components import ConfigComponent
from acex.configuration.components.interfaces import (
    # Interface,
    Loopback,
    # Physical,
    # Svi
)
from acex.configuration.components.system import (
    HostName,
    Contact,
    Location,
    DomainName
)
from acex.configuration.components.system.logging_server import LoggingBase
from acex.configuration.components.system.ntp import NtpServer
from acex.configuration.components.system.ssh import SshServer
from acex.configuration.components.network_instances import NetworkInstance, Vlan
from acex.models import ExternalValue
from acex.models.composed_configuration import ComposedConfiguration
from collections import defaultdict
from typing import Dict


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

    def _set_nested_attr(self, obj, path: str, value):
        """Set a nested attribute using dot notation path."""
        parts = path.split('.')
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)
    
    def _get_nested_attr(self, obj, path: str):
        """Get a nested attribute using dot notation path."""
        parts = path.split('.')
        for part in parts:
            obj = getattr(obj, part)
        return obj

    def add(self, component): 
        component_type = type(component)
        
        # Get mapping for this component type
        if component_type not in self.COMPONENT_MAPPING:
            raise ValueError(f"Unknown component type: {component_type.__name__}")
        
        base_path = self.COMPONENT_MAPPING[component_type]
        
        # Check if this is a dict-based component (has 'name' attribute)
        if hasattr(component, 'name') and component.name:
            # Dict-based component: interfaces, network_instances, etc.
            key = component.name
            ref_path = f"{base_path}.{key}"
            
            # Get or create the dict
            dict_obj = self._get_nested_attr(self.composed, base_path)
            
            # Set ref for external values (only if model is AttributeValue)
            if hasattr(component.model, 'is_external') and component.model.is_external():
                full_ref = f"logical_nodes.{self.logical_node_id}.{ref_path}"
                component.model.set_metadata('ref', full_ref)
            
            # Add to dict (serialize to dict for dict-based collections)
            dict_obj[key] = component.model.model_dump()
        else:
            # Simple single-value component
            ref_path = base_path
            
            # Set ref for external values (only if model is AttributeValue)
            if hasattr(component.model, 'is_external') and component.model.is_external():
                full_ref = f"logical_nodes.{self.logical_node_id}.{ref_path}"
                component.model.set_metadata('ref', full_ref)
            
            # Set the AttributeValue object directly (not serialized)
            self._set_nested_attr(self.composed, ref_path, component.model)

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
                attr_value = self._get_nested_attr(self.composed, path)
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


    def to_json(self): 
        return self.composed.model_dump()
