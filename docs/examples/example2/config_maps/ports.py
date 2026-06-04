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
                    "action": "trap"
            },
            stp_portfast=True,
            stp_bpdu_guard=True,
            stp_root_guard=True,
            switchport_mode="access",
            dtp_negotiation=False,

        )
        context.configuration.add(standard_template)



        for stack_index in range(2):
            for i in range(1, 48):
                access_port = FrontpanelPort(
                    name=f'access_port_{i}',
                    index=i,
                    stack_index=1,
                    module_index=1,
                    enabled=True,
                    switchport=True,
                    switchport_mode='access',
                    access_vlan=context.logical_node.sequence + 10,
                    negotiation=False,
                    speed=10000000,
                    auto_mdix=False,
                    stp_portfast=True,
  
                    interface_template=standard_template
                )
                context.configuration.add(access_port)


config = ConfigureAccessPorts()
config.filters = FilterAttribute("role").eq("/.*/")
