from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import Location


class SetLocation(ConfigMap): 
    def compile(self, context):

        Loc = Location(value="Test Location ABC123")
        context.configuration.add(Loc)

hostname = SetLocation()
hostname.filters = FilterAttribute("site").eq("/.*/")