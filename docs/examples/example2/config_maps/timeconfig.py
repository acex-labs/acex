from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.clock import Clock


class SetTimezone(ConfigMap):
    def compile(self, context):
        clock = Clock(
            timezone='utc',
        )
        context.configuration.add(clock)

timezone = SetTimezone()
timezone.filters = FilterAttribute("hostname").eq("/.*/")