from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.interfaces import Svi
from acex.configuration.components.vlan import Vlan


class SetMgmtVlan(ConfigMap):
    def compile(self, context):

        # Map hostname to ip address
        ip_add_map = {
            "segotsw001": "10.10.123.12/24",
            "segotsw002": "10.10.123.1/24",
            "segotsw003": "10.10.123.4/24",
            "segotsw004": "10.10.123.5/24",
            "segotsw005": "10.10.123.7/24",
            "segotsw006": "10.10.123.8/24",
            "segotsw007": "10.10.123.9/24",
            "segotsw008": "10.10.123.10/24",
            "segotsw009": "10.10.123.11/24",
        }

        # The management SVI references the management VLAN directly.
        vlan = Vlan(name="vlan_249", vlan_id=249, vlan_name="Mgmt")
        context.configuration.add(vlan)

        # Below is the mgmt vlan SVI
        mgmt_svi = Svi(
            name=f"vlan249_svi",
            vlan=vlan,
            index=0,
            description="Mgmt",
            ipv4=ip_add_map.get(context.logical_node.hostname),
        )
        context.configuration.add(mgmt_svi)

        # Export mgmt_svi so it can be referenced from other config maps
        self.mgmt_svi = mgmt_svi


mgmt_vlan = SetMgmtVlan()
mgmt_vlan.filters = (
    FilterAttribute("role").eq("lan_asw")
    | FilterAttribute("role").eq("lan_distribution")
    | FilterAttribute("role").eq("lan_csw")
)
