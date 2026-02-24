from enum import Enum
from pydantic import BaseModel
from deepdiff import DeepDiff
from typing import Any, Dict, Optional, List, Iterator

from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.configdiffer.diff import Diff, ComponentChange, AttributeChange, ComponentDiffOp



class ConfigDiffer:

    def diff(self, *, desired_config: ComposedConfiguration, observed_config: ComposedConfiguration) -> Diff:
        """
        Compare two ComposedConfiguration objects and return a component-based diff.
        
        This method identifies which ConfigComponents have been added, removed, or changed
        between the observed (current) and desired (target) configurations.
        
        Args:
            desired_config: The target configuration we want to achieve
            observed_config: The current configuration as observed on the device
            
        Returns:
            Diff: A structured diff showing added, removed, and changed components
        """
        desired_dict = self._dump_to_dicts(desired_config)
        observed_dict = self._dump_to_dicts(observed_config)

        # Hitta alla leaf-komponenter i båda configs
        desired_components = self._find_leaf_components(desired_dict)
        observed_components = self._find_leaf_components(observed_dict)

        added = []
        removed = []
        changed = []

        # Jämför component paths
        desired_paths = set(desired_components.keys())
        observed_paths = set(observed_components.keys())

        # Added components
        for path in desired_paths - observed_paths:
            comp_data = desired_components[path]
            added.append(ComponentChange(
                op=ComponentDiffOp.ADD,
                component_path=list(path),
                component_type=self._get_component_type(comp_data),
                component_name=path[-1],
                before=None,
                after=comp_data
            ))

        # Removed components
        for path in observed_paths - desired_paths:
            comp_data = observed_components[path]
            removed.append(ComponentChange(
                op=ComponentDiffOp.REMOVE,
                component_path=list(path),
                component_type=self._get_component_type(comp_data),
                component_name=path[-1],
                before=comp_data,
                after=None
            ))

        # Changed components
        for path in desired_paths & observed_paths:
            desired_comp = desired_components[path]
            observed_comp = observed_components[path]
            
            if desired_comp != observed_comp:
                attr_changes = self._get_attribute_changes(observed_comp, desired_comp)
                changed.append(ComponentChange(
                    op=ComponentDiffOp.CHANGE,
                    component_path=list(path),
                    component_type=self._get_component_type(desired_comp),
                    component_name=path[-1],
                    before=observed_comp,
                    after=desired_comp,
                    changed_attributes=attr_changes
                ))

        return Diff(added=added, removed=removed, changed=changed)

    def _dump_to_dicts(self, config: ComposedConfiguration) -> dict:
        """
        Dumps to dict, removes unnecessary keys except component_class. 
        """
        # Remove most metadata, but keep component_class for type identification
        config_dict = config.model_dump(exclude_unset=True)
        return self._clean_metadata(config_dict)
    
    def _clean_metadata(self, obj: dict) -> dict:
        """
        Recursively clean metadata but preserve component_class field.
        """
        if not isinstance(obj, dict):
            return obj
        
        cleaned = {}
        for k, v in obj.items():
            if k == "metadata":
                # Keep only component_class from metadata
                if isinstance(v, dict) and "component_class" in v:
                    cleaned["component_class"] = v["component_class"]
                continue
            
            if isinstance(v, dict):
                cleaned[k] = self._clean_metadata(v)
            elif isinstance(v, list):
                cleaned[k] = [self._clean_metadata(item) if isinstance(item, dict) else item for item in v]
            else:
                cleaned[k] = v
        
        return cleaned

    def _find_leaf_components(
        self, 
        config_dict: Dict[str, Any], 
        path: tuple = ()
    ) -> Dict[tuple, Dict[str, Any]]:
        """
        Recursively traverse config and find all leaf components.
        
        A leaf component is identified by:
        - Having a 'type' field (interfaces have type: 'ethernetCsmacd', etc.)
        - Being in a Dict[str, Component] structure (like interfaces, network_instances)
        
        Returns:
            Dict mapping path tuples to component data dicts
            Example: {('interfaces', 'GigabitEthernet0/0/1'): {...}}
        """
        components = {}
        
        if not isinstance(config_dict, dict):
            return components
        
        for key, value in config_dict.items():
            current_path = path + (key,)
            
            if not isinstance(value, dict):
                continue
            
            # Check if this dict contains components (Dict[str, Component])
            # Indicators: values are dicts with 'type' field
            if self._is_component_dict(value):
                # This is a dict of components, traverse into each
                for comp_name, comp_data in value.items():
                    if isinstance(comp_data, dict):
                        comp_path = current_path + (comp_name,)
                        components[comp_path] = comp_data
            else:
                # Check if this value itself is a component (has 'type' field)
                if 'type' in value:
                    components[current_path] = value
                else:
                    # Not a component, continue traversing
                    nested = self._find_leaf_components(value, current_path)
                    components.update(nested)
        
        return components
    
    def _is_component_dict(self, value: Dict[str, Any]) -> bool:
        """
        Check if a dict is a collection of components (Dict[str, Component]).
        
        Returns True if the dict contains component objects as values.
        """
        if not isinstance(value, dict) or not value:
            return False
        
        # Sample a few values to check
        sample_size = min(3, len(value))
        samples = list(value.values())[:sample_size]
        
        # Check if samples look like components (have 'type' field)
        component_count = sum(
            1 for v in samples 
            if isinstance(v, dict) and 'type' in v
        )
        
        # If most samples have 'type' field, this is likely a component dict
        return component_count >= len(samples) * 0.5

    def _get_component_type(self, component_data: Dict[str, Any]) -> str:
        """
        Extract the component type (class name) from component data.
        
        Tries multiple strategies:
        1. Look for explicit 'component_class' or '__class__' field
        2. Map from 'type' field to known class names
        3. Infer from structure and fields
        """
        if isinstance(component_data, dict):
            # Strategy 1: Direct class name in data
            if 'component_class' in component_data:
                return component_data['component_class']
            
            if '__class__' in component_data:
                return component_data['__class__']
            
            # Strategy 2: Map from 'type' field
            if 'type' in component_data:
                type_value = component_data['type']
                class_name = self._map_type_to_class(type_value, component_data)
                if class_name:
                    return class_name
            
            # Strategy 3: Infer from vlan_id (VLAN component)
            if 'vlan_id' in component_data:
                return "Vlan"
            
            # Strategy 4: Check for network instance indicators
            if 'route_distinguisher' in component_data or 'route_targets' in component_data:
                return "NetworkInstance"
        
        return "ConfigComponent"
    
    def _map_type_to_class(self, type_value: str, component_data: Dict[str, Any]) -> str:
        """
        Map 'type' field values to ConfigComponent class names.
        
        Args:
            type_value: The value from the 'type' field
            component_data: Full component dict for additional context
            
        Returns:
            Class name string or None if not found
        """
        # Interface type mappings
        interface_type_map = {
            "ethernetCsmacd": "FrontpanelPort",
            "ieee8023adLag": "LagInterface",
            "l3ipvlan": "Svi",
            "softwareLoopback": "Loopback",
            "subinterface": "SubInterface",
            "managementInterface": "ManagementPort",
        }
        
        if type_value in interface_type_map:
            return interface_type_map[type_value]
        
        # Add more mappings as needed
        # For other component types, we could inspect more fields
        
        return None

    def _get_attribute_changes(
        self, 
        before: Dict[str, Any], 
        after: Dict[str, Any]
    ) -> List[AttributeChange]:
        """
        Identify which specific attributes changed within a component.
        """
        changes = []
        all_keys = set(before.keys()) | set(after.keys())
        
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            
            if before_val != after_val:
                changes.append(AttributeChange(
                    attribute_name=key,
                    before=before_val,
                    after=after_val
                ))
        
        return changes