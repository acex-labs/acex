from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback


class LoopbackIf(ConfigMap):
    def compile(self, context):

        lo0 = Loopback(
            index=0,
            name="Lo0",
            description = "MPLS Loopback",
            # ipv4 = "192.0.2.3/24",
            ipv4 = context.integrations.ipam.data.ip_addresses({"hej": "verld"}),
            enabled = True
        )
        context.configuration.add(lo0)

lo = LoopbackIf()
lo.filters = FilterAttribute("hostname").eq("/.*/")
