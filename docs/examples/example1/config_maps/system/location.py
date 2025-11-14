
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import Location


class SetLocation(ConfigMap): 
    def compile(self, context):
        
        Loc = Location("HQ")
        context.configuration.add(Loc)

hostname = SetLocation()
hostname_filter = FilterAttribute("hostname").eq("/.*/")
hostname.filters = hostname_filter
