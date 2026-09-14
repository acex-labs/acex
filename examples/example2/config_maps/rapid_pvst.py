# from acex.config_map import ConfigMap, FilterAttribute
# from acex.configuration.components.spanning_tree import SpanningTreeGlobal


# class ConfigSTP(ConfigMap):
#     def compile(self, context):
#         spanningtreeglobal = SpanningTreeGlobal(
#             mode='rapid-pvst',
#             bpdu_guard=True
#         )
#         context.configuration.add(spanningtreeglobal)


# config_stp = ConfigSTP()
# config_stp.filters = FilterAttribute("hostname").eq("/.*/")
