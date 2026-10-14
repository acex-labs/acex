from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import Location


class SetLocation(ConfigMap):
    def compile(self, context):
        location = Location(value=context.logical_node.site)
        context.configuration.add(location)


config = SetLocation()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
