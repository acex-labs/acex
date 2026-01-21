from pydantic import BaseModel
from acex.models.attribute_value import AttributeValue
#from .composed_configuration import Reference
from enum import Enum
from typing import Optional, Dict

class SpanningTreeGlobalAttributes(BaseModel):
    mode: Optional[AttributeValue[str]] = None # Needs to be defined by user. Default for Cisco is RAPID-PVST and for Juniper it's just RSTP
    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    portfast: Optional[AttributeValue[bool]] = False # Disabled by default. Global setting for access ports.
    bridge_assurance: Optional[AttributeValue[bool]] = False # Disabled by default. Only supported by MST and PVRST+
    #interfaces: Optional[Dict[str, Reference]] = {}

class SpanningTreeModeConfig(BaseModel):
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bridge_priority: Optional[AttributeValue[int]] = None
    hold_count: Optional[AttributeValue[int]] = None # Range 1..10

## RSTP
class RstpAttributes(SpanningTreeModeConfig): ...

class RSTPConfig(BaseModel):
    config: RstpAttributes = RstpAttributes()

### MSTP
class MstpInstanceAttributes(BaseModel):
    instance_id: AttributeValue[int] # range: 1..4094
    name: Optional[AttributeValue[str]] = None
    vlan: Optional[AttributeValue[list[int]]] = None # List of VLANs mapped to the MST instance
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bridge_priority: Optional[AttributeValue[int]] = None

class MstpAttributes(SpanningTreeModeConfig):
    revision: Optional[AttributeValue[int]] = None
    max_hop: Optional[AttributeValue[int]] = None # Range 1..255

class MSTPConfig(BaseModel):
    config: MstpAttributes = MstpAttributes()
    mst_instances: Optional[Dict[str, MstpInstanceAttributes]] = {}

### Rapid PVST
class RapidPVSTAttributes(SpanningTreeModeConfig):
    vlan_id: Optional[AttributeValue[int]] = None  # Single VLAN ID or list of VLANs using Rapid PVST+

#class RapidPVSTVlan(BaseModel):
#    config: RapidPVSTAttributes = RapidPVSTAttributes()

class RapidPVSTConfig(BaseModel):
    vlan: Optional[Dict[str, RapidPVSTAttributes]] = {}

class SpanningTree(BaseModel):
    config: SpanningTreeGlobalAttributes = SpanningTreeGlobalAttributes()
    rstp: RSTPConfig = RSTPConfig()
    mstp: MSTPConfig = MSTPConfig()
    rapidpvst: RapidPVSTConfig = RapidPVSTConfig()

## STP interface config
#
##class SpanningTreeInterfaceConfig(BaseModel):
##    port_priority: Optional[AttributeValue[int]] = None
##    cost: Optional[AttributeValue[int]] = None
##    edge_port: Optional[AttributeValue[bool]] = False # Disabled by default
##    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
##    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
##    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
##    root_guard: Optional[AttributeValue[bool]] = False # Disabled by default
##    portfast: Optional[AttributeValue[bool]] = False # Disabled by default
##    stp_link_type: Optional[Literal["point-to-point", "shared"]] = None  # e.g., "point-to-point", "shared"
#
#class SpanningTree(BaseModel):
#    config: SpanningTreeGlobalAttributes = SpanningTreeGlobalAttributes()
#    rstp: SpanningTreeRSTPAttributes = SpanningTreeRSTPAttributes()
#    mstp: SpanningTreeMSTPAttributes = SpanningTreeMSTPAttributes()
#    rapidpvst: SpanningTreeRapidPVSTAttributes = SpanningTreeRapidPVSTAttributes()