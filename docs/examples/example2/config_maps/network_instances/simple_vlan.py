from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.vlan import Vlan

from acex.configuration.components.interfaces import Svi

class SimpleVlan(ConfigMap):
    def compile(self, context):

        vl200 = Vlan(
            name="vl200",
            vlan_id=200,
            vlan_name="vl200"
        )
        context.configuration.add(vl200)

        svi200 = Svi(
            name="vl200_svi",
            vlan=vl200,
            index=0
        )
        context.configuration.add(svi200)


vlan = SimpleVlan()
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

