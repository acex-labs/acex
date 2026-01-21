from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.spanning_tree import SpanningTreeGlobal, SpanningTreeRSTP, SpanningTreeMSTP, SpanningTreeMstpInstance, SpanningTreeRapidPVST

class STPConfig(ConfigMap):
    def compile(self, context):
        stp_global = SpanningTreeGlobal(
            mode='RAPID_PVST',
            portfast=True
        )
        context.configuration.add(stp_global)

class RSTPConfig(ConfigMap):
    def compile(self, context):
        rstp = SpanningTreeRSTP(
            bridge_priority = 32768,
            hello_time = 2,
            max_age = 20,
            forward_delay = 15,
            hold_count = 3
        )
        context.configuration.add(rstp)

class MSTConfig(ConfigMap):
    def compile(self, context):
        mstp_global = SpanningTreeMSTP(
            revision = 1,
            bridge_priority = 4096,
            hello_time = 2,
            max_age = 20,
            forward_delay = 15
        )
        context.configuration.add(mstp_global)

        mstp_instance1 = SpanningTreeMstpInstance(
            name = "MST1",
            instance_id = 1,
            vlan = [10,20,30],
            bridge_priority = 8192
        )
        context.configuration.add(mstp_instance1)

        mstp_instance2 = SpanningTreeMstpInstance(
            name = "MST2",
            instance_id = 2,
            vlan = [40,50,60],
            bridge_priority = 8192
        )
        context.configuration.add(mstp_instance2)


class RapidPVSTConfig(ConfigMap):
    def compile(self, context):
        rapid_pvst_vlan10 = SpanningTreeRapidPVST(
            name = 'VLAN10',
            vlan = 10,
            bridge_priority = 32768,
            hello_time = 2,
            max_age = 20,
            forward_delay = 15,
            hold_count = 3
        )
        context.configuration.add(rapid_pvst_vlan10)

        rapid_pvst_vlan20 = SpanningTreeRapidPVST(
            name = 'VLAN20',
            vlan = 20,
            bridge_priority = 32768,
            hello_time = 2,
            max_age = 20,
            forward_delay = 15,
            hold_count = 3
        )
        context.configuration.add(rapid_pvst_vlan20)

        rapid_pvst_vlan_range = SpanningTreeRapidPVST(
            name = 'VLAN30-40',
            vlan = [30,40],
            bridge_priority = 32768,
            hello_time = 2,
            max_age = 20,
            forward_delay = 15,
            hold_count = 3
        )
        context.configuration.add(rapid_pvst_vlan_range)

stpconfig = STPConfig()
stpconfig.filters = FilterAttribute("site").eq("/.*/")

rapidstpconfig = RSTPConfig()
rapidstpconfig.filters = FilterAttribute("site").eq("/.*/")

mstconfig = MSTConfig()
mstconfig.filters = FilterAttribute("site").eq("/.*/")

rapidpvstpconfig = RapidPVSTConfig()
rapidpvstpconfig.filters = FilterAttribute("site").eq("/.*/")