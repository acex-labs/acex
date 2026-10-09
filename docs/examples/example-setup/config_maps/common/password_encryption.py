from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import CiscoServicePasswordEncryption
from acex.configuration.components.system import SystemConfig


class SetPasswordEncryption(ConfigMap):
    def compile(self, context):
        encryption = CiscoServicePasswordEncryption(
            name="service_password_encryption",
            enabled=True,
            target=SystemConfig,
        )
        context.configuration.add(encryption)


config = SetPasswordEncryption()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
