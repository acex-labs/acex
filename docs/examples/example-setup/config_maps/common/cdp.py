from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.cdp.cdp import CdpConfig


class ConfigCDP(ConfigMap):
    def compile(self, context):
        cdpconfig = CdpConfig(
            enabled=True
        )
        context.configuration.add(cdpconfig)


config = ConfigCDP()
config.filters = (
    FilterAttribute("role").eq("access")
    | FilterAttribute("role").eq("distribution")
    | FilterAttribute("role").eq("core")
)
