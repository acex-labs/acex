# from acex.config_map import ConfigMap, FilterAttribute
# from acex.configuration.components.network_instances import VlanInstance


# class SetInterfaces(ConfigMap):
#     def compile(self, context):

#         vlan2048 = VlansInstance(
#             vlan_id=2048,
#             vlan_name='hej123',
#             name='2048'
#         )

#         g0_0_0 = InterfacesInstance(
#             name="g0/0/0",
#             interface='g0/0/0',
#             id='g0/0/0'
#         )
#         context.configuration.add(g0_0_0)


# interfaces = SetInterfaces()
# interfaces_filter = FilterAttribute("hostname").eq("/.*/")
# interfaces.filters = interfaces_filter