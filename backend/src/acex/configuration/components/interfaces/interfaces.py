
from acex.configuration.components.base_component import ConfigComponent
# from acex.models.interfaces import PhysicalInterface, VirtualInterface, SubInterfaceAttributes
from acex.models.composed_configuration import Interface as InterfaceModel
from acex.models.composed_configuration import SubInterface
from acex.models.composed_configuration import Reference
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


class Svi(Interface):
    type = "Svi"
    model_cls = SubInterface

    def pre_init(self):
        vlan = self.kwargs.pop("vlan")
        self.kwargs["vlan"] = vlan.name 

        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = Reference(
                                                        pointer="network_instances.global.interfaces",
                                                        direction="to_self"
                                                        )
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = Reference(
                                                        pointer=f"network_instances.{network_instance.name}.interfaces",
                                                        direction="to_self"
                                                        )
