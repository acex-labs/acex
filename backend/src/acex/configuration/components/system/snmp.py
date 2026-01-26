from acex.configuration.components.base_component import ConfigComponent
from acex.models.composed_configuration import ReferenceTo, ReferenceFrom
from acex.configuration.components.interfaces import Interface
from acex.configuration.components.network_instances import NetworkInstance
from acex.models.snmp import (
    SnmpConfig, 
    SnmpUser as SnmpUserAttributes,
    SnmpServer as SnmpServerAttributes,
    TrapEvent
)

class SnmpGlobal(ConfigComponent):
    type = "snmp"
    model_cls = SnmpConfig

class SnmpUser(ConfigComponent):
    type = "snmp_user"
    model_cls = SnmpUserAttributes

class SnmpServer(ConfigComponent):
    type = "snmp_trap_server"
    model_cls = SnmpServerAttributes

    def _add_vrf(self):
        #if self.kwargs.get('network_instance'):
        #    network_instance = self.kwargs.pop("network_instance")
        #    self.kwargs["network_instance"] = ReferenceFrom(pointer=f"network_instances.{network_instance.name}")
        if self.kwargs.get('network_instance'):
            ni = self.kwargs.pop("network_instance")
            if isinstance(ni, type(None)):
                pass
            elif isinstance(ni, str):
                ref = ReferenceTo(pointer=f"network_instances.{ni}")
                self.kwargs["network_instance"] = ref

            elif isinstance(ni, NetworkInstance):
                ref = ReferenceTo(pointer=f"network_instances.{ni.name}")
                self.kwargs["network_instance"] = ref

    def pre_init(self):
        self._add_vrf()
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

class SnmpTrap(ConfigComponent):
    type = "snmp_trap"
    model_cls = TrapEvent

# Traps?