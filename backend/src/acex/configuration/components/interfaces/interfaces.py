
from acex.configuration.components.base_component import ConfigComponent
from acex_devkit.models.composed_configuration import (
    EthernetCsmacdInterface,
    Ieee8023adLagInterface,
    L3IpvlanInterface,
    SoftwareLoopbackInterface,
    ManagementInterface,
    SubInterface as SubInterfaceModel,
    ReferenceFrom, 
    ReferenceTo
)

from typing import Optional

class Interface(ConfigComponent):

    def _add_vrf(self):
        if self.kwargs.get('network_instance') is None:
            self.kwargs["network_instance"] = ReferenceFrom(pointer="network_instances.global.interfaces")
        else:
            network_instance = self.kwargs.pop("network_instance")
            self.kwargs["network_instance"] = ReferenceFrom(pointer=f"network_instances.{network_instance.name}.interfaces")

    def _add_dhcp_trust(self):
        # Add reference to DHCP snooping config if exists in configmap
        if self.kwargs.get("dhcp_snooping_trust") == True:
            self.kwargs["dhcp_snooping"] = ReferenceFrom(pointer="system.dhcp.snooping.trust_interfaces")

    def _helper(self):
        if self.kwargs.get("relay_helper") is not None:
            helper = self.kwargs.pop("relay_helper")
            self.kwargs["relay_helper"] = ReferenceFrom(pointer=f"system.dhcp.relay.relay_servers.{helper.name}.interfaces")

    def _lldp_enable(self):
        if self.kwargs.get("lldp_enabled") == True:
            self.kwargs["lldp"] = ReferenceFrom(pointer="lldp.interfaces")

    def _cdp_enable(self):
        if self.kwargs.get("cdp_enabled") == True:
            self.kwargs["cdp"] = ReferenceFrom(pointer="cdp.interfaces")

    # Allow for disabling netflow on specific interface by referencing the collector
    def _netflow_disable(self):
        if self.kwargs.get("netflow_ingress_disabled") is not None:
            collector = self.kwargs.pop("netflow_ingress_disabled")
            self.kwargs["netflow"] = ReferenceFrom(pointer=f"sampling.netflow.collectors.{collector.name}.interfaces")

        if self.kwargs.get("netflow_egress_disabled") is not None:
            collector = self.kwargs.pop("netflow_egress_disabled")
            self.kwargs["netflow"] = ReferenceFrom(pointer=f"sampling.netflow.collectors.{collector.name}.interfaces")
            
    # Allow for disabling sflow on specific interface by referencing the collector
    def _sflow_disable(self):
        if self.kwargs.get("sflow_ingress_disabled") is not None:
            collector = self.kwargs.pop("sflow_ingress_disabled")
            self.kwargs["sflow"] = ReferenceFrom(pointer=f"sampling.sflow.collectors.{collector.name}.interfaces")

        if self.kwargs.get("sflow_egress_disabled") is not None:
            collector = self.kwargs.pop("sflow_egress_disabled")
            self.kwargs["sflow"] = ReferenceFrom(pointer=f"sampling.sflow.collectors.{collector.name}.interfaces")

# Keep commented for now
#class Physical(Interface):
#    type = "ethernetCsmacd"
#    model_cls = EthernetCsmacdInterface

class FrontpanelPort(Interface):
    type = "ethernetCsmacd"
    model_cls = EthernetCsmacdInterface
    def pre_init(self):
        self._add_vrf()
        self._add_dhcp_trust()
        self._helper()
        self._lldp_enable()
        self._cdp_enable()
        self._netflow_disable()
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
        self._add_dhcp_trust()
        self._helper()

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