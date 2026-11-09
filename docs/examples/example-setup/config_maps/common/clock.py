from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.clock import Clock


class SetClockConfig(ConfigMap):
    def compile(self, context):
        clock = Clock(timezone="cest 1 0")
        context.configuration.add(clock)


config = SetClockConfig()
config.filters = (
    FilterAttribute("role").eq("access")
    | FilterAttribute("role").eq("distribution")
    | FilterAttribute("role").eq("core")
)
