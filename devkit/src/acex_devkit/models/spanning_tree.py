from pydantic import BaseModel
from acex_devkit.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict

class SpanningTreeGlobalAttributes(BaseModel):
    mode: Optional[str] = None # Needs to be defined by user. Default for Cisco is RAPID-PVST and for Juniper it's just RSTP
    bpdu_filter: Optional[bool] = False # Disabled by default
    bpdu_guard: Optional[bool] = False # Disabled by default
    loop_guard: Optional[bool] = False # Disabled by default
    portfast: Optional[bool] = False # Disabled by default. Global setting for access ports.
    bridge_assurance: Optional[bool] = False # Disabled by default. Only supported by MST and PVRST+
    #interfaces: Optional[Dict[str, Reference]] = {}

class SpanningTreeModeConfig(BaseModel):
    hello_time: Optional[int] = None
    max_age: Optional[int] = None
    forward_delay: Optional[int] = None
    bridge_priority: Optional[int] = None
    hold_count: Optional[int] = None # Range 1..10

## RSTP
class RstpAttributes(SpanningTreeModeConfig): ...

class RSTPConfig(BaseModel):
    config: RstpAttributes = RstpAttributes()

### MSTP
class MstpInstanceAttributes(SpanningTreeModeConfig):
    instance_id: AttributeValue[int] # range: 1..4094
    name: Optional[AttributeValue[str]] = None
    vlan: Optional[AttributeValue[list[int]]] = None # List of VLANs mapped to the MST instance

class MstpAttributes(SpanningTreeModeConfig):
    revision: Optional[AttributeValue[int]] = None
    max_hop: Optional[AttributeValue[int]] = None # Range 1..255

class MSTPConfig(BaseModel):
    config: MstpAttributes = MstpAttributes()
    mst_instances: Optional[Dict[str, MstpInstanceAttributes]] = {}

### Rapid PVST
class RapidPVSTAttributes(SpanningTreeModeConfig):
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
    vlan: Optional[Dict[str, RapidPVSTAttributes]] = {}

class SpanningTree(BaseModel):
    config: Optional[Dict[str, SpanningTreeGlobalAttributes]] = {}#SpanningTreeGlobalAttributes()
    rstp: Optional[Dict[str, RSTPConfig]] = {}#RSTPConfig()
    mstp: Optional[Dict[str, MSTPConfig]] = {}#MSTPConfig()
    rapidpvst: Optional[Dict[str, RapidPVSTConfig]] = {}#RapidPVSTConfig()