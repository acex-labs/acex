from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.network_instances import L2Domain, Vlan, L2Vlan


# Simple L2 vlan
class L2DomainWVlans(ConfigMap):
    def compile(self, context):

        vlan = L2Vlan(
            name = "vlan_mgmt",
            vlan_id = 100,
            vlan_name = "vlan_mgmt"
        )
        vlan2 = L2Vlan(
            name = "other_vlan",
            vlan_id = 101,
            vlan_name = "vlan_101"
        )

        vlan2049 = L2Domain(
            name="mgmt",
            vlans = [vlan, vlan2]
        )

        context.configuration.add(vlan2049)

vlans = L2DomainWVlans()
vlans_filter = FilterAttribute("hostname").eq("R1")
vlans.filters = vlans_filter

#TODO: Attach l2domain to interface: ... 