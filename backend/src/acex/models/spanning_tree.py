from pydantic import BaseModel
from acex.models.attribute_value import AttributeValue
from .composed_configuration import Reference, ReferenceFrom, ReferenceTo
from enum import Enum
from typing import Optional, Dict

class SpanningTreeModeConfig(BaseModel):
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bridge_priority: Optional[AttributeValue[int]] = None

class SpanningTreeGlobal(SpanningTreeModeConfig):
    mode: Optional[AttributeValue[SpanningTreeMode]] = "RSTP"
    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    #interfaces: Optional[Dict[str, Reference]] = {}

class SpanningTreeMode(str, Enum): 
    RSTP = "RSTP"
    MSTP = "MSTP"
    PVST = "PVST"
    PVST_PLUS = "PVST_PLUS"

class SpanningTreeRSTP(SpanningTreeModeConfig): 
    interfaces: Optional[Dict[str, Reference]] = {}

class SpanningTreeMSTP(SpanningTreeModeConfig):
    interfaces: Optional[Dict[str, Reference]] = {}
    mst_instances: Optional[Dict[str, Reference]] = {}
    vlan: Optional[Dict[str, Reference]] = {}

class SpanningTreeRapidPVST(SpanningTreeModeConfig):
    interfaces: Optional[Dict[str, Reference]] = {}
    vlan: Optional[Dict[str, Reference]] = {}

# How use this per interface?
class SpanningTreeInterfaceConfig(BaseModel):
    port_priority: Optional[AttributeValue[int]] = None
    cost: Optional[AttributeValue[int]] = None
    edge_port: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    root_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    portfast: Optional[AttributeValue[bool]] = False # Disabled by default
    link_type: Optional[AttributeValue[str]] = None  # e.g., "point-to-point", "shared"