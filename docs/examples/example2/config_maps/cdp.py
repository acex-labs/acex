from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.cdp import CdpConfig
from acex.configuration.components.interfaces import FrontpanelPort

class CdpConfigMap(ConfigMap):
    def compile(self, context):
        
        intf123 = FrontpanelPort(
            name="Ethernet1/1",
            description="Uplink to Core",
            index=1,
            cdp_enabled=True
        )

        context.configuration.add(intf123)

        intf321 = FrontpanelPort(
            name="Ethernet1/2",
            description="Uplink to Core",
            index=2,
            cdp_enabled=True
        )

        context.configuration.add(intf321)

        cdp_config = CdpConfig(
            enabled=True,
            transmit_interval=30,
            hold_time=120,
            advertise_v2=False
        )

        context.configuration.add(cdp_config)

cdp_config = CdpConfigMap()
cdp_config.filters = FilterAttribute("site").eq("/.*/")