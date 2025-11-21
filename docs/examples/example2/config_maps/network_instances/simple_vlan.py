# from acex.config_map import ConfigMap, FilterAttribute
# from acex.configuration.components.network_instances import Vlan, L2Domain
# from acex.configuration.components.interfaces import Svi

# # Simple L2 vlan
# # An instance of Vlan is a composition done behind the scenes that creates
# # both a l2domain and l2vlan and ties them together 1:1.
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

