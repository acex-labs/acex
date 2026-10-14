from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system import DomainName
from acex.configuration.components.system.dns import DnsServer


class SetDNGlobal(ConfigMap):
    def compile(self, context):
        domain_name = DomainName(value="example.net")
        context.configuration.add(domain_name)

        dns_servers = (
            ("dns_1", "1.1.1.1"),
            ("dns_2", "2.2.2.2"),
            ("dns_3", "3.3.3.3"),
            ("dns_4", "4.4.4.4"),
        )
        for name, address in dns_servers:
            context.configuration.add(DnsServer(name=name, address=address))


config = SetDNGlobal()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
