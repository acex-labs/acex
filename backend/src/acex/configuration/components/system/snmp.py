from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.configuration.components.network_instances import L3Vrf
from acex_devkit.models.composed_configuration import (
    SnmpConfig, 
    SnmpUser as SnmpUserAttributes,
    SnmpServer as SnmpServerAttributes,
    TrapEvent,
    SnmpCommunity as SnmpCommunityAttributes,
    SnmpView as SnmpViewAttributes,
    ReferenceTo, 
    ReferenceFrom
)
from acex.configuration.components.acl.acl import Ipv4Acl, Ipv6Acl

class SnmpGlobal(ConfigComponent):
    type = "snmp"
    model_cls = SnmpConfig

class SnmpUser(ConfigComponent):
    type = "snmp_user"
    model_cls = SnmpUserAttributes

class SnmpServer(ConfigComponent):
    type = "snmp_trap_server"
    model_cls = SnmpServerAttributes

    #def _add_vrf(self):
    #    if self.kwargs.get('network_instance'):
    #        ni = self.kwargs.pop("network_instance")
    #        if isinstance(ni, type(None)):
    #            pass
    #        elif isinstance(ni, str):
    #            ref = ReferenceFrom(pointer=f"network_instances.{ni}")
    #            self.kwargs["network_instance"] = ref
#
    #        elif isinstance(ni, L3Vrf):
    #            ref = ReferenceFrom(pointer=f"network_instances.{ni.name}")
    #            self.kwargs["network_instance"] = ref

    def pre_init(self):
        # Resolve source_interface
        if "source_interface" in self.kwargs:
            si = self.kwargs.pop("source_interface")
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref

        if self.kwargs.get("ipv6acl") is not None:
            acl = self.kwargs.pop("ipv6acl")
            if isinstance(acl, type(None)):
                pass
            elif isinstance(acl, str):
                self.kwargs["ipv6acl"] = ReferenceTo(pointer=f"acl.ipv6_acls.{acl}")
            elif isinstance(acl, Ipv6Acl):
                self.kwargs["ipv6acl"] = ReferenceTo(
                    pointer=f"acl.ipv6_acls.{acl.name}"
                )

class SnmpTrap(ConfigComponent):
    type = "snmp_trap"
    model_cls = TrapEvent

class SnmpCommunity(ConfigComponent):
    type = "snmp_community"
    model_cls = SnmpCommunityAttributes

    def pre_init(self):
        # Resolve source_interface
        if "source_interface" in self.kwargs:
            si = self.kwargs.pop("source_interface")
            if isinstance(si, type(None)):
                pass
            elif isinstance(si, str):
                ref = ReferenceTo(pointer=f"interfaces.{si}")
                self.kwargs["source_interface"] = ref

            elif isinstance(si, Interface):
                ref = ReferenceTo(pointer=f"interfaces.{si.name}")
                self.kwargs["source_interface"] = ref
        
        # Resolve view
        if "view" in self.kwargs:
            v = self.kwargs.pop("view")
            if isinstance(v, type(None)):
                pass
            elif isinstance(v, str):
                ref = ReferenceTo(pointer=f"system.snmp.views.{v}")
                self.kwargs["view"] = ref

            elif isinstance(v, SnmpView):
                ref = ReferenceTo(pointer=f"system.snmp.views.{v.name}")
                self.kwargs["view"] = ref

        if self.kwargs.get("ipv4acl") is not None:
            acl = self.kwargs.pop("ipv4acl")
            if isinstance(acl, type(None)):
                pass
            elif isinstance(acl, str):
                self.kwargs["ipv4acl"] = ReferenceTo(pointer=f"acl.ipv4_acls.{acl}")
            elif isinstance(acl, Ipv4Acl):
                self.kwargs["ipv4acl"] = ReferenceTo(
                    pointer=f"acl.ipv4_acls.{acl.name}"
                )
                
class SnmpView(ConfigComponent):
    type = "snmp_view"
    model_cls = SnmpViewAttributes