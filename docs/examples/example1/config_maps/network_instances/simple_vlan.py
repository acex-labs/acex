from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.network_instances import L2Domain, Vlan


# Simple L2 vlan
# An instance of Vlan is a composition done behind the scenes that creates
# both a l2domain and l2vlan and ties them together 1:1.
class SimpleVlan(ConfigMap):
    def compile(self, context):

        vlan = Vlan(
            name = "vlan_200",
            vlan_id = 200,
            vlan_name = "vlan_twohundred"
        )

        context.configuration.add(vlan)

vlan = SimpleVlan()
vlan_filter = FilterAttribute("hostname").eq("R1")
vlan.filters = vlan_filter

