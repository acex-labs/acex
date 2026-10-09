from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaServerGroup,
    aaaTacacs,
)

# import managmenet-vlan object for reference
from config_maps.common.mgmt_vlan import mgmt_vlan

TACACS_SERVER_GROUP_NAME = 'ISE-TACACS+'

class SetTacacsConfig(ConfigMap):
    def compile(self, context):
        server_group = aaaServerGroup(
            name = 'ISE-TACACS+',
            enable = True,
            type = 'tacacs'
        )
        context.configuration.add(server_group)

        tacacs = aaaTacacs(
            name = "ISE-VIP",
            address = '123.12.13.11',
            source_interface = mgmt_vlan.mgmt_svi,
            server_group = server_group
        )
        context.configuration.add(tacacs)
        
        self.tacacs = server_group

config = SetTacacsConfig()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)

