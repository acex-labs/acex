from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.vtp import Vtp


class ConfigVTP(ConfigMap):
    def compile(self, context):

        site = context.logical_node.site
        vtp = Vtp(
            mode='server',
            version=3,
            password='ExampleVTP',
            domain_name=f'{site}'
        )
        context.configuration.add(vtp)


config_vtp = ConfigVTP()
config_vtp.filters = FilterAttribute("role").eq("lan_csw")
