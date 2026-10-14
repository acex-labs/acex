from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.spanning_tree import SpanningTreeGlobal


class ConfigSTP(ConfigMap):
    def compile(self, context):
        spanning_tree = SpanningTreeGlobal(
            mode="rapid-pvst",
            bpdu_guard=True,
            bpdu_filter=False,
            portfast=True,
            bridge_assurance=False,
            loop_guard=False,
        )
        context.configuration.add(spanning_tree)


config = ConfigSTP()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
