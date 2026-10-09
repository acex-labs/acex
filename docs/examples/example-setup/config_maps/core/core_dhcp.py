from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.network_instances.network_instances import L3Vrf
from acex.configuration.components.system.dhcp import (
    DHCPSnooping,
    DhcpRelayServer
)

from acex.configuration.components.vlan import Vlan
from acex.configuration.components.interfaces import FrontpanelPort, Svi

class SetDhcpConfig(ConfigMap):
    def compile(self, context):
        
        hlp_emea1 = DhcpRelayServer(
            name="EMEA1",
            address="10.123.41.8"
        )
        context.configuration.add(hlp_emea1)

        hlp_emea2 = DhcpRelayServer(
            name="EMEA2",
            address="10.123.31.9"
        )
        context.configuration.add(hlp_emea2)


core_dhcp = SetDhcpConfig()
core_dhcp.filters = (FilterAttribute("role").eq("lan_csw"))