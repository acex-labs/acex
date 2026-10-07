from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.lldp.lldp import LldpConfig


class ConfigLLDP(ConfigMap):
    def compile(self, context):
        lldpconfig = LldpConfig(
            enabled=True
        )
        context.configuration.add(lldpconfig)


config = ConfigLLDP()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
