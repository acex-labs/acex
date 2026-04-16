from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.dhcp import (
    DHCPSnooping
)

from acex.configuration.components.vlan import Vlan
from acex.configuration.components.interfaces import FrontpanelPort

class SetDhcpConfig(ConfigMap):
    def compile(self, context):
        # Global relay enable (optional if your renderer expects it)
        dc_snoop = DHCPSnooping(
            name="DHCP_snooping",
            enabled=True,
            option82=True, 
            #vlans=[10, 20] # reference?
        )
        context.configuration.add(dc_snoop)

        vlan10 = Vlan(
            name="Vlan10",
            vlan_id=10,
            dhcp_snooping_trust=True # This will add reference to DHCP snooping config
        )
        context.configuration.add(vlan10)

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
            dhcp_snooping_trust=True # This will add reference to DHCP snooping config
        )
        context.configuration.add(if0_test)


autolab_dhcp = SetDhcpConfig()
autolab_dhcp.filters = FilterAttribute("site").eq("test_site_123")