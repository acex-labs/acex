
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.vlans import Vlans


class SetVlans(ConfigMap): 
    def compile(self, context):
        
        vlan200 = Vlans(
            name='vlan_200',
            vlan_id=200,
            vlan_name='management'
        )
        context.configuration.add(vlan200)

        vlan300 = Vlans(
            name='vlan_300',
            vlan_id=300,
            vlan_name='servers'
        )

        context.configuration.add(vlan300)

vlans = SetVlans()
vlans_filter = FilterAttribute("hostname").eq("/.*/")
vlans.filters = vlans_filter