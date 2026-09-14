from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.vlan import Vlan
from acex.configuration.components.interfaces import FrontpanelPort



class TrunkPort(ConfigMap):
    def compile(self, context):
        port = FrontpanelPort(
            name="my_trunk",
            index=47,
            switchport=True
        )
        context.configuration.add(port)



trunk = TrunkPort()
trunk.filters = FilterAttribute("hostname").eq("R1")

