from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces.interfaces import Svi
from acex.configuration.components.network_instances.network_instances import L3Vrf
from acex.configuration.components.system.dhcp import (
    DHCPSnooping,
    DhcpRelayServer
)

from acex.configuration.components.vlan import Vlan
from acex.configuration.components.interfaces import FrontpanelPort

class SetDhcpConfig(ConfigMap):
    def compile(self, context):
        test_vrf = L3Vrf(
            name="test"
        )
        context.configuration.add(test_vrf)

        # Global relay enable (optional if your renderer expects it)
        dc_snoop = DHCPSnooping(
            name="DHCP_snooping",
            enabled=True,
            option82=True, 
        )
        context.configuration.add(dc_snoop)

        hlp_1 = DhcpRelayServer(
            name="DHCP_HELPER_VLAN10_SRV1",
            address="192.168.1.254",
            network_instance=test_vrf
        )
        context.configuration.add(hlp_1)

        vlan10 = Vlan(
            name="Vlan10",
            vlan_id=10,
            dhcp_snooping_trust=True, # This will add reference to DHCP snooping config
        )
        context.configuration.add(vlan10)

        svi10 = Svi(
            name="Vlan10",
            index=0,
            vlan=vlan10,
            enabled=True,
            ipv4='192.168.100.123/24',
            network_instance=test_vrf,
            dhcp_snooping_trust=True, # This will add reference to DHCP snooping config
            relay_helper=hlp_1 # This will add reference to DHCP relay helper # works
            )
        context.configuration.add(svi10)

        if0_test = FrontpanelPort(
            index=1,
            stack_index=1,
            module_index=1,
            name="if0_test",
            speed=1000000,
            description="Switchport1",
            switchport = True,
            switchport_mode = "access",
            access_vlan = 10,
            mtu = 1500,
            negotiation = True,
            lldp_enabled = False,
            cdp_enabled = False,
            proxy_arp = False,
            redirects = False,
            dhcp_snooping_trust=True, # This will add reference to DHCP snooping config
            relay_helper=hlp_1 # This will add reference to DHCP relay helper address # does not work
        )
        context.configuration.add(if0_test)

autolab_dhcp = SetDhcpConfig()
autolab_dhcp.filters = FilterAttribute("site").eq("test_site_123")
