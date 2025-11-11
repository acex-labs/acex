
from acex.configuration.components.base_component import ConfigComponent
from acex.models.network_instances import InterfacesAttributes, VlansAttributes

class GlobalInstance(ConfigComponent): ...

class InterfacesInstance(GlobalInstance):
    type = "interfaces"
    model_cls = InterfacesAttributes

class VlansInstance(GlobalInstance):
    type = "vlans"
    model_cls = VlansAttributes

#class GlobalInstance(Interface):
#    type = "softwareLoopback"
#    model_cls = Global




