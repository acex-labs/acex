from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Physical


class Frontpanel(ConfigMap):
    def compile(self, context):


        ip = context.integrations.ipam.data.ip_addresses({"id": 27})
        # ip = 
        # routed uplink
        if0 = Physical(
            index=0,
            name="if0",
            speed=1000000,
            description="Routed uplink to core",
            switchport = False,
            ipv4 = context.integrations.ipam.data.ip_addresses({"id": 28})
        )
        context.configuration.add(if0)

        # routed uplink
        if47 = Physical(
            index=47,
            name="if47",
            speed=1000000,
            description="Routed uplink to core",
            switchport = False,
            ipv4 = ip,
            enabled=False
        )
        context.configuration.add(if47)


fp = Frontpanel()
fp.filters = FilterAttribute("role").eq("core")