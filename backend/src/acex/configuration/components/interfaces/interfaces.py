
from acex.configuration.components.base_component import ConfigComponent
# from acex.models.interfaces import PhysicalInterface, VirtualInterface, SubInterfaceAttributes
from acex.models.composed_configuration import (
    EthernetCsmacdInterface,
    Ieee8023adLagInterface,
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    ManagementInterface,
    SubInterface as SubInterfaceModel
)

from acex.models.composed_configuration import ReferenceFrom, ReferenceTo
from typing import Optional

class Interface(ConfigComponent):

    def _add_vrf(self):
        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = ReferenceFrom(pointer="network_instances.global.interfaces")
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = ReferenceFrom(pointer=f"network_instances.{network_instance.name}.interfaces")


# Keep commented for now
#class Physical(Interface):
#    type = "ethernetCsmacd"
#    model_cls = EthernetCsmacdInterface

class FrontpanelPort(Interface):
    type = "ethernetCsmacd"
    model_cls = EthernetCsmacdInterface
    def pre_init(self):
        self._add_vrf()
        # Resolve referenced etherchannel if any
        #print('self.kwargs: ', self.kwargs)
        #if "etherchannel" in self.kwargs:
        #    print('self.kwargs: ', self.kwargs)
        #    ec = self.kwargs.pop("etherchannel")
        #    if isinstance(ec, type(None)):
        #        pass
        #    elif isinstance(ec, str):
        #        ref = ReferenceTo(pointer=f"interfaces.{ec}")
        #        #print("ref: ", ref)
        #        self.kwargs["etherchannel"] = ref
        #    elif isinstance(ec, LagInterface):
        #        #print("ref: ", ref)
        #        self.kwargs["etherchannel"] = ReferenceTo(pointer=f"interfaces.{ec.name}")

class ManagementPort(Interface):
    type = "ManagementInterface"
    model_cls = ManagementInterface

    # VRF can be set on mgmt interfaces. Usually "mgmt" but can be something else depending on device and vendor.
    def pre_init(self):
        self._add_vrf()

class LagInterface(Interface):
    """
    WIP :) 
    """
    type = "ieee8023adLag"
    model_cls = Ieee8023adLagInterface

    #def pre_init(self):
    #    # Resolve referenced interfaces if any
    #    if "etherchannel" in self.kwargs:

class Svi(Interface):
    type = "l3ipvlan"
    model_cls = L3IpvlanInterface

    def pre_init(self):
        referenced_vlan = self.kwargs.pop("vlan")
        self.kwargs["vlan_id"] = referenced_vlan.model.vlan_id.value
        self._add_vrf()



class Loopback(Interface):
    type = "softwareLoopback"
    model_cls = SoftwareLoopbackInterface

    def pre_init(self):
        self._add_vrf()

class Subinterface(Interface):
    type = "subinterface"
    model_cls = SubInterfaceModel

    def pre_init(self):
        vlan = self.kwargs.pop("vlan")
        self.kwargs["vlan"] = vlan.name 
        self.kwargs["vlan_id"] = vlan.model.vlan_id.value
        self._add_vrf()