from acex.configuration.components.system.ntp import NtpServer

from acex.config_map import ConfigMap, FilterAttribute


class SetNtpServer(ConfigMap):
    def compile(self, context):
        ntp_server = NtpServer(
            name="NTP",
            address="ntp.example.net"
        )
        context.configuration.add(ntp_server)


config = SetNtpServer()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
