"""
Example: How drivers can use ComponentDiff to render device-specific patches.

This demonstrates how a network element driver can use the component-based diff
to generate device configuration commands.
"""

from typing import List
from acex_devkit.configdiffer import ConfigDiffer, ComponentChange, ComponentDiffOp


class CiscoIOSPatchRenderer:
    """
    Example patch renderer for Cisco IOS devices.
    
    This demonstrates how drivers can map ComponentChange objects to
    device-specific commands based on component types and operations.
    """
    
    def render_patch(self, component_change: ComponentChange) -> List[str]:
        """
        Render a ComponentChange into Cisco IOS commands.
        
        Args:
            component_change: The component change to render
            
        Returns:
            List of IOS commands to apply the change
        """
        # Route to specific handler based on component type
        handler_map = {
            "Loopback": self._render_loopback,
            "FrontpanelPort": self._render_interface,
            "Vlan": self._render_vlan,
            "L3Vrf": self._render_vrf,
            # Add more component types as needed
        }
        
        handler = handler_map.get(component_change.component_type)
        if handler:
            return handler(component_change)
        else:
            # Fallback for unknown component types
            return [f"! Unknown component type: {component_change.component_type}"]
    
    def _render_loopback(self, change: ComponentChange) -> List[str]:
        """Render Loopback interface changes"""
        commands = []
        
        if change.op == ComponentDiffOp.ADD:
            # Option 1: Use serialized data dict
            commands.append(f"interface {change.component_name}")
            if change.after.get("description"):
                commands.append(f"  description {change.after['description']}")
            if change.after.get("ipv4"):
                commands.append(f"  ip address {change.after['ipv4']}")
            commands.append("  no shutdown")
            
            # Option 2: Use actual ConfigComponent object
            if change.after_object:
                # Access component methods and properties directly
                comp = change.after_object
                commands.append(f"interface {comp.name}")
                if hasattr(comp.model, 'description') and comp.model.description:
                    commands.append(f"  description {comp.model.description.value}")
                if hasattr(comp.model, 'ipv4') and comp.model.ipv4:
                    commands.append(f"  ip address {comp.model.ipv4.value}")
            
        elif change.op == ComponentDiffOp.REMOVE:
            # Removing a loopback
            commands.append(f"no interface {change.component_name}")
            
        elif change.op == ComponentDiffOp.CHANGE:
            # Modifying existing loopback - can use object for advanced logic
            commands.append(f"interface {change.component_name}")
            
            # Option 1: Simple approach using changed_attributes
            for attr_change in change.changed_attributes:
                if attr_change.attribute_name == "description":
                    if attr_change.after is None:
                        commands.append(f"  no description")
                    else:
                        commands.append(f"  description {attr_change.after}")
                        
                elif attr_change.attribute_name == "ipv4":
                    if attr_change.after is None:
                        commands.append(f"  no ip address")
                    else:
                        commands.append(f"  ip address {attr_change.after}")
            
            # Option 2: Advanced approach using component objects
            if change.after_object and change.before_object:
                # Can compare objects, call methods, etc.
                after_comp = change.after_object
                before_comp = change.before_object
                
                # Example: Check if component has a custom method
                if hasattr(after_comp, 'get_config_commands'):
                    commands.extend(after_comp.get_config_commands())
        
        return commands
    
    def _render_interface(self, change: ComponentChange) -> List[str]:
        """Render physical interface changes"""
        commands = []
        
        if change.op == ComponentDiffOp.CHANGE:
            commands.append(f"interface {change.component_name}")
            
            # Only render changed attributes
            for attr_change in change.changed_attributes:
                if attr_change.attribute_name == "description":
                    if attr_change.after is None:
                        commands.append(f"  no description")
                    else:
                        commands.append(f"  description {attr_change.after}")
                        
                elif attr_change.attribute_name == "mtu":
                    commands.append(f"  mtu {attr_change.after}")
                    
                elif attr_change.attribute_name == "enabled":
                    if attr_change.after:
                        commands.append(f"  no shutdown")
                    else:
                        commands.append(f"  shutdown")
        
        # Note: Physical interfaces typically cannot be added/removed
        # so we mainly handle CHANGE operations
        
        return commands
    
    def _render_vlan(self, change: ComponentChange) -> List[str]:
        """Render VLAN changes"""
        commands = []
        
        if change.op == ComponentDiffOp.ADD:
            commands.append(f"vlan {change.component_name}")
            if change.after.get("name"):
                commands.append(f"  name {change.after['name']}")
                
        elif change.op == ComponentDiffOp.REMOVE:
            commands.append(f"no vlan {change.component_name}")
            
        elif change.op == ComponentDiffOp.CHANGE:
            commands.append(f"vlan {change.component_name}")
            for attr_change in change.changed_attributes:
                if attr_change.attribute_name == "name":
                    commands.append(f"  name {attr_change.after}")
        
        return commands
    
    def _render_vrf(self, change: ComponentChange) -> List[str]:
        """Render VRF changes"""
        commands = []
        
        if change.op == ComponentDiffOp.ADD:
            commands.append(f"vrf definition {change.component_name}")
            if change.after.get("rd"):
                commands.append(f"  rd {change.after['rd']}")
                
        elif change.op == ComponentDiffOp.REMOVE:
            commands.append(f"no vrf definition {change.component_name}")
            
        elif change.op == ComponentDiffOp.CHANGE:
            commands.append(f"vrf definition {change.component_name}")
            for attr_change in change.changed_attributes:
                if attr_change.attribute_name == "rd":
                    commands.append(f"  rd {attr_change.after}")
        
        return commands


# Example usage
def example_usage():
    """
    Example of how a driver would use ConfigDiffer and render patches.
    """
    from acex_devkit.models.composed_configuration import ComposedConfiguration
    
    # Assume we have two configurations
    observed_config = ComposedConfiguration(...)  # Current device config
    desired_config = ComposedConfiguration(...)   # Target config
    
    # Create differ and compute diff
    differ = ConfigDiffer()
    diff = differ.diff(
        desired_config=desired_config,
        observed_config=observed_config
    )
    
    # Create patch renderer
    renderer = CiscoIOSPatchRenderer()
    
    # Generate all commands
    all_commands = []
    
    # Render additions
    for change in diff.added:
        commands = renderer.render_patch(change)
        all_commands.extend(commands)
    
    # Render changes
    for change in diff.changed:
        commands = renderer.render_patch(change)
        all_commands.extend(commands)
    
    # Render removals
    for change in diff.removed:
        commands = renderer.render_patch(change)
        all_commands.extend(commands)
    
    # Now all_commands contains the complete configuration patch
    print("\n".join(all_commands))
    
    # Or you can be more selective:
    # Only render interface changes
    interface_changes = diff.get_changes_by_path_prefix(['interfaces'])
    for change in interface_changes:
        commands = renderer.render_patch(change)
        print("\n".join(commands))
