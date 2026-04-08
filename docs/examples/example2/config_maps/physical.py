from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import FrontpanelPort


class PhysicalPort(ConfigMap):
    def compile(self, context):

        if0 = FrontpanelPort(
            index=0,
            name="if0",
            speed=1000000,
            description="Switchport1",
            switchport = True
        )
        context.configuration.add(if0)

intf = PhysicalPort()
intf.filters = FilterAttribute("hostname").eq("/.*/")