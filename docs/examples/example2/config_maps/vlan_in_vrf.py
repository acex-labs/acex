from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.vlan import Vlan
from acex.configuration.components.network_instances import L3Vrf
from acex.configuration.components.interfaces import Svi


class VlanInVrf(ConfigMap):
    def compile(self, context):

        vrf = L3Vrf(
            name="my_vrf"
        )
        context.configuration.add(vrf)

        vl300 = Vlan(
            name="vl300",
            vlan_id=300,
            vlan_name="vl300"
        )
        context.configuration.add(vl300)

        svi300 = Svi(
            name="vl300_svi",
            vlan=vl300,
            index=1,
            network_instance=vrf,
            ipv4 = "192.0.2.1/24"
        )
        context.configuration.add(svi300)



vlan = VlanInVrf()
vlan.filters = FilterAttribute("hostname").eq("R1")





