from acex.config_map import ConfigMap, FilterAttribute
from acex.configuration.components.vlan import Vlan
from acex.configuration.components.interfaces import Svi

# vlans = [1,11,128,129,248,249,260,280,285,291]
vlan_to_network = {
    1: "",
    11: "10.123.19.0/28",
    128: "10.123.4.0/24",
    129: "10.123.8.0/24",
    248: "10.123.0.0/24",
    249: "10.123.5.0/24",
    260: "10.123.6.0/24",
    280: "10.123.8.0/24",
    285: "10.123.9.0/24",
    291: "10.123.10.0/24",
}


class VlanSviConfigMap(ConfigMap):
    def compile(self, context):
        for vlan_id, network in vlan_to_network.items():
            vlan_obj = Vlan(
                name=f"vl{vlan_id}", vlan_id=vlan_id, vlan_name=f"vl{vlan_id}"
            )
            context.configuration.add(vlan_obj)

            if not network:
                continue

            logical_node_seq = context.logical_node.sequence
            address, prefix = network.split("/")
            base = address.rsplit(".", 1)[0]
            svi = Svi(
                name=f"svi{vlan_id}",
                index=0,
                vlan=vlan_obj,
                description=f"svi{vlan_id}",
                ipv4=f"{base}.{logical_node_seq}/{prefix}",
            )
            context.configuration.add(svi)


vlan_svi_config = VlanSviConfigMap()
vlan_svi_config.filters = FilterAttribute("site").eq("lan_asw")
