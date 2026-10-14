from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.aaa import (
    aaaServerGroup,
    aaaRadius,
)

# import managmenet-vlan object for reference
from config_maps.common.mgmt_vlan import mgmt_vlan

RADIUS_SERVER_GROUP_NAME = 'RADIUS-GROUP-NEW'

class SetRadiusConfig(ConfigMap):
    def compile(self, context):
        server_group = aaaServerGroup(
            name = 'RADIUS-GROUP-NEW',
            enable = True,
            type = 'radius'
        )
        context.configuration.add(server_group)

        radius = aaaRadius(
            name = "ISE-VIP",
            address = '10.14.123.12',
            source_interface = mgmt_vlan.mgmt_svi,
            server_group = server_group,
            timeout=5
        )
        context.configuration.add(radius)
        
        self.radius = server_group

config = SetRadiusConfig()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)

