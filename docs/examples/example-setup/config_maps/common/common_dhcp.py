from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.dhcp import (
    DHCPSnooping,
)
from acex.configuration.components.augments.cisco import CiscoDhcpSnoopingTrackServer


class SetDhcpConfig(ConfigMap):
    def compile(self, context):

        dhcp_snooping = DHCPSnooping(
            name="common_dhcp_snooping",
            enabled=True,
            option82=False,
        )
        context.configuration.add(dhcp_snooping)

        dhcp_tracking = CiscoDhcpSnoopingTrackServer(
            all_dhcp_acks=True,
            target=dhcp_snooping,
        )
        context.configuration.add(dhcp_tracking)


common_dhcp = SetDhcpConfig()
common_dhcp.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
