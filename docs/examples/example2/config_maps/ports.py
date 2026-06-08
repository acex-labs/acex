from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, InterfaceTemplate


class ConfigureAccessPorts(ConfigMap):
    def compile(self, context):

        standard_template = InterfaceTemplate(
            name="Standard",
            description="Standard",
            storm_control={
                "broadcast_pps": 250,
                "multicast_pps": 1000,
                "unknown_unicast_pps": 200,
                "action": "trap",
            },
            stp_portfast=True,
            stp_bpdu_guard=True,
            stp_root_guard=True,
            switchport_mode="access",
            dtp_negotiation=False,
        )
        context.configuration.add(standard_template)

        for stack_index in range(2):
            for i in range(0, 48):  # will count 0 - 47
                access_port = FrontpanelPort(
                    name=f"access_port_{stack_index}_{i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=0,
                    enabled=True,
                    switchport=True,
                    switchport_mode="access",
                    access_vlan=context.logical_node.sequence + 10,
                    negotiation=False,
                    speed=10000000,
                    auto_mdix=False,
                    stp_portfast=True,
                    description=f"Access port {i} on stack {stack_index}",
                    interface_template=standard_template,
                )
                context.configuration.add(access_port)

            # for stack_index in range(2):
            for i in range(0, 4):  # will count 48 - 51
                trunk_port = FrontpanelPort(
                    name=f"trunk_port_{stack_index}_{i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=1,
                    enabled=True,
                    switchport=True,
                    switchport_mode="trunk",
                    trunk_allowed_vlans=[
                        context.logical_node.sequence + 10,
                        context.logical_node.sequence + 20,
                    ],
                    negotiation=False,
                    speed=10000000,
                    auto_mdix=False,
                    stp_portfast=True,
                    description=f"Trunk port {i} on stack {stack_index}",
                    # interface_template=standard_template
                )
                context.configuration.add(trunk_port)


config = ConfigureAccessPorts()
config.filters = FilterAttribute("role").eq("/.*/")
