from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.lldp import LldpConfig, LldpInterface
from acex.configuration.components.interfaces import FrontpanelPort

class LldpConfigMap(ConfigMap):
    def compile(self, context):
        
        intf0 = FrontpanelPort(
            name="Ethernet1/1",
            description="Uplink to Core",
            index=1,
            lldp_enabled=True
        )

        context.configuration.add(intf0)

        lldp_config = LldpConfig(
            enabled=True,
            transmit_interval=30,
            hold_time=120
        )

        context.configuration.add(lldp_config)

lldp_config = LldpConfigMap()
lldp_config.filters = FilterAttribute("site").eq("/.*/")