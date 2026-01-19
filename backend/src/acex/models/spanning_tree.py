from pydantic import BaseModel
from acex.models.attribute_value import AttributeValue
#from .composed_configuration import Reference, ReferenceFrom, ReferenceTo
from enum import Enum
from typing import Optional, Dict

class SpanningTreeModeConfig(BaseModel):
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bridge_priority: Optional[AttributeValue[int]] = None
    hold_count: Optional[AttributeValue[int]] = None # Range 1..10

class SpanningTreeGlobalAttributes(BaseModel):
    mode: Optional[AttributeValue[str]] = None # Needs to be defined by user. Default for Cisco is RAPID-PVST and for Juniper it's just RSTP
    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    portfast: Optional[AttributeValue[bool]] = False # Disabled by default. Global setting for access ports.
    bridge_assurance: Optional[AttributeValue[bool]] = False # Disabled by default. Only supported by MST and PVRST+
    #interfaces: Optional[Dict[str, Reference]] = {}

class SpanningTreeMode(str, Enum): 
    RSTP = "RSTP"
    MSTP = "MSTP"
    #PVST = "PVST"
    RAPID_PVST = "RAPID_PVST"

class SpanningTreeRSTPAttributes(SpanningTreeModeConfig):
    name = "RSTP"
#    interfaces: Optional[Dict[str, Reference]] = {}

class MstInstanceConfig(BaseModel):
    instance_id: AttributeValue[int] # range: 1..4094
    #name: Optional[AttributeValue[str]] = None
    vlan: Optional[AttributeValue[list[int]]] = None # List of VLANs mapped to the MST instance
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bridge_priority: Optional[AttributeValue[int]] = None

class SpanningTreeMSTPAttributes(SpanningTreeModeConfig):
    name = "MSTP"
    revision: Optional[AttributeValue[int]] = None
    max_hop: Optional[AttributeValue[int]] = None # Range 1..255
    mst_instances: Optional[Dict[str, MstInstanceConfig]] = {}

#    interfaces: Optional[Dict[str, Reference]] = {}
#    mst_instances: Optional[Dict[str, Reference]] = {}
#    vlan: Optional[Dict[str, Reference]] = {}

class SpanningTreeRapidPVSTAttributes(SpanningTreeModeConfig):
    name = "RAPID_PVST"
    vlan: Optional[AttributeValue[list[int]]] = None # List of VLANs using Rapid PVST+
#    interfaces: Optional[Dict[str, Reference]] = {}
#    vlan: Optional[Dict[str, Reference]] = {}

#class SpanningTreeInterfaceConfig(BaseModel):
#    port_priority: Optional[AttributeValue[int]] = None
#    cost: Optional[AttributeValue[int]] = None
#    edge_port: Optional[AttributeValue[bool]] = False # Disabled by default
#    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
#    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
#    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
#    root_guard: Optional[AttributeValue[bool]] = False # Disabled by default
#    portfast: Optional[AttributeValue[bool]] = False # Disabled by default
#    stp_link_type: Optional[Literal["point-to-point", "shared"]] = None  # e.g., "point-to-point", "shared"