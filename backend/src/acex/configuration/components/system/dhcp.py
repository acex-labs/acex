from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    DhcpRelayServerAttributes,
    DHCPSnoopingAttributes,
)


class DHCPSnooping(ConfigComponent):
    type = "dhcp_snooping"
    model_cls = DHCPSnoopingAttributes

    def pre_init(self):
        # VLANs may be given as Vlan components or as VLAN IDs.
        vlans = self.kwargs.get("vlans")
        if vlans is not None:
            self.kwargs["vlans"] = [v if isinstance(v, int) else v.model.vlan_id.value for v in vlans]


class DhcpRelayServer(ConfigComponent):
    type = "dhcp_relay_server"
    model_cls = DhcpRelayServerAttributes

    def pre_init(self):
        network_instance = self.kwargs.pop("network_instance", None)
        if network_instance is None:
            self.kwargs["network_instance"] = "global"
        elif isinstance(network_instance, str):
            self.kwargs["network_instance"] = network_instance
        else:
            self.kwargs["network_instance"] = network_instance.name
