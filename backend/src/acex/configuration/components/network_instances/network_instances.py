
from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.configuration.components.vlan import Vlan

from acex.models.composed_configuration import (
    NetworkInstance
)


class L3Vrf(ConfigComponent): 
    type = "l3vrf"
    model_cls = NetworkInstance


class L2Domain(ConfigComponent):
    type = "l2vsi"
    model_cls = NetworkInstance

