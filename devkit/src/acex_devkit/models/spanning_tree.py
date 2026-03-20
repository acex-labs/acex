from pydantic import BaseModel
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_model import ContainerModel
from enum import Enum
from typing import ClassVar, Optional, Dict

class SpanningTreeGlobalAttributes(ContainerModel, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    mode: Optional[AttributeValue[str]] = None # Needs to be defined by user. Default for Cisco is RAPID-PVST and for Juniper it's just RSTP
    bpdu_filter: Optional[AttributeValue[bool]] = None # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = None # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = None # Disabled by default
    portfast: Optional[AttributeValue[bool]] = None # Disabled by default. Global setting for access ports.
    bridge_assurance: Optional[AttributeValue[bool]] = None # Disabled by default. Only supported by MST and PVRST+
    #interfaces: Optional[Dict[str, Reference]] = None

class SpanningTreeModeConfig(BaseModel):
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bridge_priority: Optional[AttributeValue[int]] = None
    hold_count: Optional[AttributeValue[int]] = None # Range 1..10

## RSTP
class RstpAttributes(ContainerModel, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ()

class RSTPConfig(BaseModel):
    #config: RstpAttributes = RstpAttributes()
    config: Optional[Dict[str, RstpAttributes]] = None

### MSTP
class MstpInstanceAttributes(ContainerModel, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ("instance_id",)
    instance_id: AttributeValue[int] # range: 1..4094
    name: Optional[AttributeValue[str]] = None
    vlan: Optional[AttributeValue[list[int]]] = None # List of VLANs mapped to the MST instance

class MstpAttributes(ContainerModel, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    revision: Optional[AttributeValue[int]] = None
    max_hop: Optional[AttributeValue[int]] = None # Range 1..255

class MSTPConfig(BaseModel):
    #config: MstpAttributes = MstpAttributes()
    config: Optional[Dict[str, MstpAttributes]] = None
    mst_instances: Optional[Dict[str, MstpInstanceAttributes]] = None

### Rapid PVST
class RapidPVSTAttributes(ContainerModel, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ("vlan",)
    """
    Docstring for RapidPVSTAttributes
    vlan can be a string or list. Depending on how NED is built it will check wether it's a single VLAN or multiple VLANs and then format the data to the correct format
    for the command of the specific vendor.
    For example for Cisco:
    * Single VLAN
        spanning-tree vlan 10 priority 8192
    * Multiple VLANs
        spanning-tree vlan 10-30 priority 8192
    """
    #vlan_id: Optional[AttributeValue[int]] = None  # Single VLAN ID or list of VLANs using Rapid PVST+
    vlan: Optional[AttributeValue[int | list[int]]] = None  # Single VLAN ID or list of VLANs using Rapid PVST+

class RapidPVSTConfig(BaseModel):
    vlan: Optional[Dict[str, RapidPVSTAttributes]] = None

class SpanningTree(BaseModel):
    config: Optional[Dict[str, SpanningTreeGlobalAttributes]] = None#SpanningTreeGlobalAttributes()
    rstp: Optional[RSTPConfig] = RSTPConfig()
    mstp: Optional[MSTPConfig] = MSTPConfig()
    rapidpvst: Optional[RapidPVSTConfig] = RapidPVSTConfig()