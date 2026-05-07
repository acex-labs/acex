
from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import CiscoServicePasswordEncryption
from acex.configuration.components.system import SystemConfig

class SetPWEnc(ConfigMap):
    def compile(self, context):

        encryption = CiscoServicePasswordEncryption(
            name="pwe",
            enabled=True,
            target=SystemConfig(),
        )

        context.configuration.add(encryption)


pwe = SetPWEnc()
pwe.filters = FilterAttribute("hostname").eq("/.*/")# & FilterAttribute("hostname").ne("R2")
