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
            network_instance=vrf
        )
        context.configuration.add(svi300)


vlan = VlanInVrf()
vlan.filters = FilterAttribute("hostname").eq("R2")















# class SimpleVlan(ConfigMap):
#     def compile(self, context):

#         # ni = L2Domain(
#         #     name="min_instance"
#         # )
#         # context.configuration.add(ni)

#         # Vlan in given l2domain:
#         # vl = Vlan(
#         #     name = "vlan_in_global_domain",
#         #     vlan_id = 300,
#         #     vlan_name="test_vlan_in_domain",
#         # )
#         # context.configuration.add(vl)

#         # vlan with given network_instance
#         vl = Vlan(
#             name = "my_vlan",
#             vlan_id = 301,
#             vlan_name="vlan_301",
#         )
#         context.configuration.add(vl)

#         # add svi
#         svi = Svi(
#             name="mitt_svi",
#             vlan=vl,
#         )
#         context.configuration.add(svi)




# vlan = SimpleVlan()
# vlan_filter = FilterAttribute("hostname").eq("R1")
# vlan.filters = vlan_filter

