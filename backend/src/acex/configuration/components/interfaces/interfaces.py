
from acex.configuration.components.base_component import ConfigComponent
# from acex.models.interfaces import PhysicalInterface, VirtualInterface, SubInterfaceAttributes
from acex.models.composed_configuration import Interface as InterfaceModel
from typing import Optional

class Interface(ConfigComponent): ...


# class Physical(Interface):
#     type = "ethernetCsmacd"
#     model_cls = PhysicalInterface

# class SubInterface(ConfigComponent):
#     type = "subinterface"
#     model_cls = SubInterfaceAttributes
#     vlan: Optional["Vlan"]
#     network_instance: Optional["NetworkInstance"]

# class Svi(SubInterface):
#     type = "svi"
#     model_cls = SubInterfaceAttributes
#     vlan: "Vlan"

class Loopback(Interface):
    type = "softwareLoopback"
    model_cls = InterfaceModel


