from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.vtp import VTP

class VtpConfig(ConfigMap):
    def compile(self, context):
        vtp = VTP(
            domain_name='example_domain',
            mode='client', # can be 'server', 'client', 'transparent' or 'off'
            version=3,
            password='example_password'
        )
        context.configuration.add(vtp)

vtpconfig = VtpConfig()
vtpconfig.filters = FilterAttribute("site").eq("/.*/")