
from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.configuration.components.network_instances.network_instances import L3Vrf
from acex.configuration.components.vlan import Vlan

from acex_devkit.models.composed_configuration import (
    DHCPSnoopingAttributes,
    DhcpRelayServerAttributes,
    ReferenceFrom,
    ReferenceTo,
)

class DHCPSnooping(ConfigComponent): 
    type = "dhcp_snooping"
    model_cls = DHCPSnoopingAttributes

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