from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.spanning_tree import SpanningTreeGlobal, SpanningTreeRSTP, SpanningTreeMSTP, SpanningTreeRapidPVST

class STPConfig(ConfigMap):
    def compile(self, context):
        stp_global = SpanningTreeGlobal(
            mode='RAPID_PVST',
            portfast=True
        )
        context.configuration.add(stp_global)

class RapidPVSTConfig(ConfigMap):
    def compile(self, context):
        rapid_pvst = SpanningTreeRapidPVST(
            vlan=[10, 20, 30],
            bridge_priority=4096
        )
        context.configuration.add(rapid_pvst)

stpconfig = STPConfig()
stpconfig.filters = FilterAttribute("site").eq("/.*/")