from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort


class PhysicalPort(ConfigMap):
    def compile(self, context):

        if0 = FrontpanelPort(
            index=1,
            stack_index=1,
            module_index=1,
            name="if0",
            speed=1000000,
            description="Switchport1",
            switchport = True,
            switchport_mode = "access",
            access_vlan = 10,
            mtu = 1500,
            negotiation = True,
            lldp_enabled = False,
            cdp_enabled = False
        )
        context.configuration.add(if0)

        if1 = Physical(
            index=1,
            module_index=0,
            stack_index=0,
            name="if1",
            speed=1000000,
            description="Switchport2",
            switchport = True,
            switchport_mode = "trunk",
            trunk_allowed_vlans = [10,20],
            native_vlan = 123,
            mtu = 1500,
            negotiation = True,
            lldp_enabled = True,
            cdp_enabled = True
        )
        context.configuration.add(if1)

intf = PhysicalPort()
intf.filters = FilterAttribute("hostname").eq("/.*/")