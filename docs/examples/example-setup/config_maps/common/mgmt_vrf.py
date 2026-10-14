from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.network_instances import L3Vrf


class SetMgmtVRF(ConfigMap):
    def compile(self, context):
        vrf = L3Vrf(
            name="Mgmt-vrf"
        )
        context.configuration.add(vrf)


config = SetMgmtVRF()
config.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)