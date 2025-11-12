from acex.config_map import ConfigMap, FilterAttribute
<<<<<<< HEAD
<<<<<<< HEAD
from acex.configuration.components.system.ntp import NtpServer
=======
from acex.configuration.components.system.ntp import NTPServer
>>>>>>> 4ccc9e1 (Add support for ntp)
=======
from acex.configuration.components.system.ntp import NtpServer
>>>>>>> 3fccc02 (Changed so that variable and class names follow pascal/peb8 standard)


class NtpConfig(ConfigMap):
    def compile(self, context):

<<<<<<< HEAD
<<<<<<< HEAD
        ntp1 = NtpServer(
=======
        ntp1 = NTPServer(
>>>>>>> 4ccc9e1 (Add support for ntp)
=======
        ntp1 = NtpServer(
>>>>>>> 3fccc02 (Changed so that variable and class names follow pascal/peb8 standard)
            name='se.pool.ntp.org',
            address='se.pool.ntp.org',
            prefer=True
        )
        context.configuration.add(ntp1)

<<<<<<< HEAD
<<<<<<< HEAD
        ntp2 = NtpServer(
=======
        ntp2 = NTPServer(
>>>>>>> 4ccc9e1 (Add support for ntp)
=======
        ntp2 = NtpServer(
>>>>>>> 3fccc02 (Changed so that variable and class names follow pascal/peb8 standard)
            name='fi.pool.ntp.org',
            address='fi.pool.ntp.org',
            prefer=True
        )
        context.configuration.add(ntp2)

ntpconfig = NtpConfig()
ntpconfig_filter = FilterAttribute("hostname").eq("/.*/")
ntpconfig.filters = ntpconfig_filter