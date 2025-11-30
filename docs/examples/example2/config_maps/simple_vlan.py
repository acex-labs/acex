from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.vlan import Vlan

from acex.configuration.components.interfaces import Svi

class SimpleVlan(ConfigMap):
    def compile(self, context):

        vl200 = Vlan(
            name="vl200",
            vlan_id=200,
            vlan_name="vl200"
        )
        context.configuration.add(vl200)

        svi200 = Svi(
            name="vl200_svi",
            vlan=vl200,
            index=0
        )
        context.configuration.add(svi200)


vlan = SimpleVlan()
vlan.filters = FilterAttribute("hostname").eq("R2")
