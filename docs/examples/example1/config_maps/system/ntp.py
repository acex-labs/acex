from acex.config_map import ConfigMap, FilterAttribute
<<<<<<< HEAD
from acex.configuration.components.system.ntp import NtpServer
=======
from acex.configuration.components.system.ntp import NTPServer
>>>>>>> 4ccc9e1 (Add support for ntp)


class NtpConfig(ConfigMap):
    def compile(self, context):

<<<<<<< HEAD
        ntp1 = NtpServer(
=======
        ntp1 = NTPServer(
>>>>>>> 4ccc9e1 (Add support for ntp)
            name='se.pool.ntp.org',
            address='se.pool.ntp.org',
            prefer=True
        )
        context.configuration.add(ntp1)

<<<<<<< HEAD
        ntp2 = NtpServer(
=======
        ntp2 = NTPServer(
>>>>>>> 4ccc9e1 (Add support for ntp)
            name='fi.pool.ntp.org',
            address='fi.pool.ntp.org',
            prefer=True
        )
        context.configuration.add(ntp2)

ntpconfig = NtpConfig()
ntpconfig_filter = FilterAttribute("hostname").eq("/.*/")
ntpconfig.filters = ntpconfig_filter