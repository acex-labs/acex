"""
Example demonstrating the component-based diff workflow.

This shows how the diff model works end-to-end:
1. ConfigDiffer compares two ComposedConfiguration objects
2. Returns ComponentDiff with added/removed/changed components
3. Driver uses ComponentChange objects to render device commands
"""

from acex_devkit.configdiffer import ConfigDiffer, ComponentDiff, ComponentChange, ComponentDiffOp


def example_diff_structure():
    """
    Example showing what a ComponentDiff looks like after comparing configs.
    """
    
    # After running: diff = differ.diff(desired_config=..., observed_config=...)
    # You get a ComponentDiff with this structure:
    
    example_diff = {
        "added": [
            {
                "op": "add",
                "component_path": ["interfaces", "Loopback1"],
                "component_type": "Loopback",
                "component_name": "Loopback1",
                "before": None,
                "after": {
                    "name": "Loopback1",
                    "description": "New loopback",
                    "ipv4": "10.0.0.1/32",
                    "enabled": True
                }
            }
        ],
        "removed": [
            {
                "op": "remove",
                "component_path": ["vlans", "100"],
                "component_type": "Vlan",
                "component_name": "100",
                "before": {
                    "vlan_id": 100,
                    "name": "OLD_VLAN"
                },
                "after": None
            }
        ],
        "changed": [
            {
                "op": "change",
                "component_path": ["interfaces", "GigabitEthernet0/0/1"],
                "component_type": "FrontpanelPort",
                "component_name": "GigabitEthernet0/0/1",
                "before": {
                    "name": "GigabitEthernet0/0/1",
                    "description": "Old description",
                    "enabled": False,
                    "mtu": 1500
                },
                "after": {
                    "name": "GigabitEthernet0/0/1",
                    "description": "New description",  # Changed
                    "enabled": True,  # Changed
                    "mtu": 1500
                },
                "changed_attributes": [
                    {
                        "attribute_name": "description",
                        "before": "Old description",
                        "after": "New description"
                    },
                    {
                        "attribute_name": "enabled",
                        "before": False,
                        "after": True
                    }
                ]
            }
        ]
    }
    
    return example_diff


def driver_render_example(change: ComponentChange) -> list[str]:
    """
    Example showing how a driver renders a CHANGE operation.
    
    For CHANGE operations:
    - before: contains the complete component as observed on device
    - after: contains the complete component as desired
    - changed_attributes: lists which specific attributes changed
    
    The driver can choose:
    1. Use changed_attributes to render only what changed (efficient)
    2. Use before/after to apply custom logic based on full context
    """
    commands = []
    
    if change.op == ComponentDiffOp.CHANGE:
        # Example 1: Use changed_attributes (simple approach)
        if change.component_type == "FrontpanelPort":
            commands.append(f"interface {change.component_name}")
            
            for attr in change.changed_attributes:
                if attr.attribute_name == "description":
                    commands.append(f"  description {attr.after}")
                elif attr.attribute_name == "enabled":
                    if attr.after:
                        commands.append(f"  no shutdown")
                    else:
                        commands.append(f"  shutdown")
        
        # Example 2: Use full before/after for complex logic
        elif change.component_type == "L3Vrf":
            # Some changes might require complex logic
            # Access full context through before/after
            
            old_rd = change.before.get("rd")
            new_rd = change.after.get("rd")
            
            if old_rd != new_rd:
                # RD change might require special handling
                commands.append(f"vrf definition {change.component_name}")
                if old_rd:
                    commands.append(f"  no rd {old_rd}")
                if new_rd:
                    commands.append(f"  rd {new_rd}")
    
    return commands


def workflow_example():
    """
    Complete workflow example from configs to rendered commands.
    """
    
    print("=" * 70)
    print("Component-Based Diff Workflow")
    print("=" * 70)
    
    print("\n1. ConfigDiffer jämför två ComposedConfiguration objekt:")
    print("   - observed_config (nuvarande på enheten)")
    print("   - desired_config (målkonfiguration)")
    
    print("\n2. ConfigDiffer returnerar ComponentDiff med:")
    print("   - added: Lista av komponenter som ska läggas till")
    print("   - removed: Lista av komponenter som ska tas bort")
    print("   - changed: Lista av komponenter som har ändrats")
    
    print("\n3. För varje ComponentChange får vi:")
    print("   - op: 'add', 'remove', eller 'change'")
    print("   - component_path: ['interfaces', 'GigabitEthernet0/0/1']")
    print("   - component_type: 'FrontpanelPort', 'Loopback', etc.")
    print("   - component_name: Namnet på komponenten")
    
    print("\n4. För CHANGE operationer:")
    print("   - before: Hela objektet FÖRE ändringen")
    print("   - after: Hela objektet EFTER ändringen")
    print("   - changed_attributes: Lista av ändrade attribut med före/efter värden")
    
    print("\n5. Driver använder ComponentChange för att rendera kommandon:")
    print("   - Mappning: component_type -> render_method")
    print("   - Drivrutinen kan välja att:")
    print("     a) Använda changed_attributes för effektiva patches")
    print("     b) Använda before/after för komplex logik")
    
    print("\n" + "=" * 70)
    print("Exempel: Interface change")
    print("=" * 70)
    
    # Simulera en ändring
    from acex_devkit.configdiffer.component_diff import AttributeChange
    
    change = ComponentChange(
        op=ComponentDiffOp.CHANGE,
        component_path=["interfaces", "GigabitEthernet0/0/1"],
        component_type="FrontpanelPort",
        component_name="GigabitEthernet0/0/1",
        before={
            "name": "GigabitEthernet0/0/1",
            "description": "Old description",
            "enabled": False,
            "mtu": 1500
        },
        after={
            "name": "GigabitEthernet0/0/1",
            "description": "New description",
            "enabled": True,
            "mtu": 1500
        },
        changed_attributes=[
            AttributeChange(
                attribute_name="description",
                before="Old description",
                after="New description"
            ),
            AttributeChange(
                attribute_name="enabled",
                before=False,
                after=True
            )
        ]
    )
    
    print("\nComponentChange:")
    print(f"  Type: {change.component_type}")
    print(f"  Name: {change.component_name}")
    print(f"  Operation: {change.op}")
    print(f"\n  Changed attributes:")
    for attr in change.changed_attributes:
        print(f"    - {attr.attribute_name}: {attr.before} → {attr.after}")
    
    print("\nRendered commands:")
    commands = driver_render_example(change)
    for cmd in commands:
        print(f"  {cmd}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    workflow_example()
