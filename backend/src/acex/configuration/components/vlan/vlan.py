
from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import Vlan as VlanAttributes

class Vlan(ConfigComponent): 
    type = "l2vlan"
    model_cls = VlanAttributes

    def pre_init(self):
        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = "global"
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = network_instance.name 








# -from acex.models.network_instances import VlanAttributes
# -from typing import Optional
 
 
# -class Vlan(ConfigComponent): 
# -    type = "l2vlan"
# -    model_cls = VlanAttributes
# -    interfaces: Optional["Subinterface"] = None
# -
# -    def pre_init(self):
# -        if self.kwargs.get('network_instance') is None:
# -            self.kwargs["network_instance"] = "global"
# -        else:
# -            network_instance = self.kwargs.pop("network_instance")
# -            self.kwargs["network_instance"] = network_instance.name 