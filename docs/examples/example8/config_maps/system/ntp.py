from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.ntp import NtpServer

class NtpConfig(ConfigMap):
    def compile(self, context):
        ntp1 = NtpServer(
            name='server4321.example.com',
            address='10.123.123.26',
            prefer=True
        )
        context.configuration.add(ntp1)
        
        ntp2 = NtpServer(
            name='server1234.example.com',
            address='10.123.123.27',
            prefer=False
        )
        context.configuration.add(ntp2)

ntpconfig = NtpConfig()
ntpconfig.filters = FilterAttribute("site").eq("/.*/")