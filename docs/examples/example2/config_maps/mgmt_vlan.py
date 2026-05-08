from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Svi
from acex.configuration.components.network_instances import Vlan




class SetMgmtVlan(ConfigMap):
    def compile(self, context):


        # Map hostname to ip address
        ip_add_map = {
            "test-sw01": "192.168.1.1/24",
            "test-sw02": "192.168.1.2/24",
            "test-sw03": "192.168.1.3/24",
        }


        # At the moment we need to define the vlan for mgmt SVI here as we otherweise can't make the connection.
        vlan = Vlan(
            name = 'vlan_1232',
            vlan_id = 1232, 
            vlan_name = 'Mgmt'
        )
        context.configuration.add(vlan)
        
        # Below is the mgmt vlan SVI
        mgmt_svi = Svi(
            name=f'vlan1232_svi', 
            vlan=vlan,
            index=0,
            description='Mgmt',
            ipv4=ip_add_map.get(context.logical_node.hostname)
        )
        context.configuration.add(mgmt_svi)
        
        # Export mgmt_svi so it can be referenced from other config maps
        self.mgmt_svi = mgmt_svi

mgmt_vlan = SetMgmtVlan()
mgmt_vlan.filters = FilterAttribute("site").eq("/.*/")
