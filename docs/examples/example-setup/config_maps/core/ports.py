from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, InterfaceTemplate


class ConfigureCorePorts(ConfigMap):
    def compile(self, context):
        max_no_of_stacks = 9

        for stack_index in range(max_no_of_stacks):
            for i in range(0, 48):
                access_port = FrontpanelPort(
                    name=f"downlink_port_{stack_index}_{i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=0,
                    enabled=True,
                    switchport=True,
                    switchport_mode="trunk",
                    negotiation=False,
                    speed=10000000,
                    auto_mdix=False,
                    stp_portfast=False,
                    description=f"Downlink Port {i}",
                )
                context.configuration.add(access_port)
            for i in range(0, 4):
                uplink_port = FrontpanelPort(
                    name=f"Uplink port {i}",
                    index=i,
                    stack_index=stack_index,
                    module_index=1,
                    enabled=True,
                    switchport=True,
                    switchport_mode="trunk",
                    negotiation=False,
                    speed=25000000,
                    auto_mdix=False,
                    stp_portfast=False,
                    description=f"Uplink Port {i}",
                )
                context.configuration.add(uplink_port)


config = ConfigureCorePorts()
config.filters = FilterAttribute("role").eq("lan_csw")
