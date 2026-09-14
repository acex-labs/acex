from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.dhcp import DHCPSnooping
from acex.configuration.components.augments.cisco import CiscoDhcpSnoopingTrackServer


class SetDhcpSnooping(ConfigMap):
    def compile(self, context):
        snooping = DHCPSnooping(
            enabled=True,
            option82=False,
        )
        context.configuration.add(snooping)

        context.configuration.add(
            CiscoDhcpSnoopingTrackServer(all_dhcp_acks=True)
        )


config = SetDhcpSnooping()
config.filters = FilterAttribute("role").eq("/.*/")