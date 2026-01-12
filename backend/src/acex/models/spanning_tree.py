from pydantic import BaseModel
from acex.models.attribute_value import AttributeValue
from .composed_configuration import Reference, ReferenceFrom, ReferenceTo
from enum import Enum
from typing import Optional, Dict

class SpanningTreeConfig(BaseModel):
    mode: Optional[AttributeValue[SpanningTreeMode]] = None
    bridge_priority: Optional[AttributeValue[int]] = None
    hello_time: Optional[AttributeValue[int]] = None
    max_age: Optional[AttributeValue[int]] = None
    forward_delay: Optional[AttributeValue[int]] = None
    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    interfaces: Optional[Dict[str, Reference]] = {}

class SpanningTreeMode(str, Enum): 
    RSTP = "RSTP"
    MSTP = "MSTP"
    PVST = "PVST"
    PVST_PLUS = "PVST_PLUS"

#class SpanningTreeBpduFilter(str, Enum):
#    ENABLED = "ENABLED"
#    DISABLED = "DISABLED"  
#
#class SpanningTreeBpduGuard(str, Enum):
#    ENABLED = "ENABLED"
#    DISABLED = "DISABLED"

# How use this per interface?
class SpanningTreeInterfaceConfig(BaseModel):
    port_priority: Optional[AttributeValue[int]] = None
    cost: Optional[AttributeValue[int]] = None
    edge_port: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_filter: Optional[AttributeValue[bool]] = False # Disabled by default
    bpdu_guard: Optional[AttributeValue[bool]] = False # Disabled by default
    loop_guard: Optional[AttributeValue[bool]] = False # Disabled by default