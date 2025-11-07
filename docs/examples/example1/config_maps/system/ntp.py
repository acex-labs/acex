from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.ntp import NTPServer


class NtpConfig(ConfigMap):
    def compile(self, context):

        ntp1 = NTPServer(
            name='se.pool.ntp.org',
            address='se.pool.ntp.org',
            prefer=True
        )
        context.configuration.add(ntp1)

        ntp2 = NTPServer(
            name='fi.pool.ntp.org',
            address='fi.pool.ntp.org',
            prefer=True
        )
        context.configuration.add(ntp2)

ntpconfig = NtpConfig()
ntpconfig_filter = FilterAttribute("hostname").eq("/.*/")
ntpconfig.filters = ntpconfig_filter