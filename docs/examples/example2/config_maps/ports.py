from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort, InterfaceTemplate


class ConfigureAccessPorts(ConfigMap):
    def compile(self, context):

        # Reusable template for the LAN access ports.
        # Shared attributes go here; per-port stuff (name, index, stack_index, module_index)
        # stays on the FrontpanelPort instance below.

        standard_template = InterfaceTemplate(
            name="standard_template",
            description="Standard"
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
                    access_vlan=12,
                    negotiation=False,
                    speed=10000000,
                    interface_template=standard_template
                )
                context.configuration.add(access_port)


config = ConfigureAccessPorts()
config.filters = FilterAttribute("role").eq("lan_access")
