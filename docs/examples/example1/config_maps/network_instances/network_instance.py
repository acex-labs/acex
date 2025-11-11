from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.network_instances import InterfacesInstance, VlansInstance

class SetVlans(ConfigMap):
    def compile(self, context):

        vlan2048 = VlansInstance(
            vlan_id=2048,
            vlan_name='hej123',
            name='2048'
        )

        context.configuration.add(vlan2048)

        vlan2049 = VlansInstance(
            vlan_id=2049,
            vlan_name='mgmt',
            name='2049'
        )

        context.configuration.add(vlan2049)

class SetInterfaces(ConfigMap):
    def compile(self, context):

        g0_0_0 = InterfacesInstance(
            name="g0/0/0",
            interface='g0/0/0',
            id='g0/0/0'
        )
        context.configuration.add(g0_0_0)

vlans = SetVlans()
vlans_filter = FilterAttribute("hostname").eq("/.*/")
vlans.filters = vlans_filter

interfaces = SetInterfaces()
interfaces_filter = FilterAttribute("hostname").eq("/.*/")
interfaces.filters = interfaces_filter