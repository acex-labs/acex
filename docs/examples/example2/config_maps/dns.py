from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.system.dns import DnsServer
from acex.configuration.components.network_instances import L3Vrf

class DnsConfigMap(ConfigMap):
    def compile(self, context):
        test_vrf = L3Vrf(
            name="TestVRF",
        )
        context.configuration.add(test_vrf)

        dns_server1 = DnsServer(
            name="DNS Server 1",
            address="1.1.1.1",
        )
        context.configuration.add(dns_server1)

        dns_server2 = DnsServer(
            name="DNS Server 2",
            address="2.2.2.2",
            network_instance=test_vrf
        )
        context.configuration.add(dns_server2)

dns_config = DnsConfigMap()
dns_config.filters = FilterAttribute("site").eq("/.*/")