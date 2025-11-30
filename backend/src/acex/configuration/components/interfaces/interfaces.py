
from acex.configuration.components.base_component import ConfigComponent
# from acex.models.interfaces import PhysicalInterface, VirtualInterface, SubInterfaceAttributes
from acex.models.composed_configuration import (
    EthernetCsmacdInterface,
    Ieee8023adLagInterface,
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    SubInterface as SubInterfaceModel
)

from acex.models.composed_configuration import Reference
from typing import Optional

class Interface(ConfigComponent): ...


class Physical(Interface):
    type = "ethernetCsmacd"
    model_cls = EthernetCsmacdInterface

class LagInterface(Interface):
    """
    WIP :) 
    """
    ...

class Svi(Interface):
    type = "l3ipvlan"
    model_cls = L3IpvlanInterface

class Loopback(Interface):
    type = "softwareLoopback"
    model_cls = SoftwareLoopbackInterface

    def pre_init(self):
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


class Subinterface(Interface):
    type = "subinterface"
    model_cls = SubInterfaceModel

    def pre_init(self):
        vlan = self.kwargs.pop("vlan")
        self.kwargs["vlan"] = vlan.name 
        self.kwargs["vlan_id"] = vlan.model.vlan_id.value


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

