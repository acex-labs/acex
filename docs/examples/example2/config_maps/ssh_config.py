from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.augments.cisco import CiscoSshDhMinSize

class SetSSHDhMinSize(ConfigMap):
    def compile(self, context):
        dh_min_size = CiscoSshDhMinSize(
            dh_min_size=2048
        )

        context.configuration.add(dh_min_size)

dh_min_size = SetSSHDhMinSize()
dh_min_size.filters = FilterAttribute("role").eq("/.*/")