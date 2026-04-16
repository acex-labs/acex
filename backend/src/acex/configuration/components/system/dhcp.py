
from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.configuration.components.vlan import Vlan

from acex_devkit.models.composed_configuration import (
    DHCPSnoopingAttributes
)

class DHCPSnooping(ConfigComponent): 
    type = "dhcp_snooping"
    model_cls = DHCPSnoopingAttributes