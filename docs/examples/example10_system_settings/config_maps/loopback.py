from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Loopback


class MPLSLoopback(ConfigMap):
    def compile(self, context):
        port = Loopback(
            name="MPLS_LO",
            index=0
        )
        context.configuration.add(port)

lo = MPLSLoopback()
lo.filters = FilterAttribute("hostname").eq("/.*/")

