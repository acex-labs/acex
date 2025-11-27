
from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.configuration.components.vlan import Vlan

from acex.models.network_instances import (
    NetworkInstanceAttributes,
    L2DomainAttributes,
    VlanAttributes,
)


class NetworkInstance(ConfigComponent): 
    vlans: dict[str, Vlan]
    interfaces: dict[str, Interface]


class L2Domain(NetworkInstance): 
    type = "l2vsi"
    model_cls = L2DomainAttributes



# L3Domain för vrf stöd