from typing import ClassVar

from pydantic import BaseModel

from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_entry import ContainerEntry


class SpanningTreeGlobalAttributes(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    # Needs to be defined by user. Default for Cisco is RAPID-PVST and for Juniper it's just RSTP
    mode: AttributeValue[str] | None = None
    bpdu_filter: AttributeValue[bool] | None = None  # Disabled by default
    bpdu_guard: AttributeValue[bool] | None = None  # Disabled by default
    loop_guard: AttributeValue[bool] | None = None  # Disabled by default
    portfast: AttributeValue[bool] | None = None  # Disabled by default. Global setting for access ports.
    bridge_assurance: AttributeValue[bool] | None = None  # Disabled by default. Only supported by MST and PVRST+
    # interfaces: Optional[Dict[str, Reference]] = None


class SpanningTreeModeConfig(BaseModel):
    hello_time: AttributeValue[int] | None = None
    max_age: AttributeValue[int] | None = None
    forward_delay: AttributeValue[int] | None = None
    bridge_priority: AttributeValue[int] | None = None
    hold_count: AttributeValue[int] | None = None  # Range 1..10


## RSTP
class RstpAttributes(ContainerEntry, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ()


class RSTPConfig(BaseModel):
    # config: RstpAttributes = RstpAttributes()
    config: dict[str, RstpAttributes] | None = None


### MSTP
class MstpInstanceAttributes(ContainerEntry, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ("instance_id",)
    instance_id: AttributeValue[int]  # range: 1..4094
    name: AttributeValue[str] | None = None
    vlan: AttributeValue[list[int]] | None = None  # List of VLANs mapped to the MST instance


class MstpAttributes(ContainerEntry, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ()
    revision: AttributeValue[int] | None = None
    max_hop: AttributeValue[int] | None = None  # Range 1..255


class MSTPConfig(BaseModel):
    # config: MstpAttributes = MstpAttributes()
    config: dict[str, MstpAttributes] | None = None
    mst_instances: dict[str, MstpInstanceAttributes] | None = None


### Rapid PVST
class RapidPVSTAttributes(ContainerEntry, SpanningTreeModeConfig):
    identity_fields: ClassVar[tuple[str, ...]] = ("vlan",)
    """
    Docstring for RapidPVSTAttributes
    vlan can be a string or list. Depending on how NED is built it will check wether it's a single
    VLAN or multiple VLANs and then format the data to the correct format
    for the command of the specific vendor.
    For example for Cisco:
    * Single VLAN
        spanning-tree vlan 10 priority 8192
    * Multiple VLANs
        spanning-tree vlan 10-30 priority 8192
    """
    # vlan_id: Optional[AttributeValue[int]] = None  # Single VLAN ID or list of VLANs using Rapid PVST+
    vlan: AttributeValue[int | list[int]] | None = None  # Single VLAN ID or list of VLANs using Rapid PVST+


class RapidPVSTConfig(BaseModel):
    vlan: dict[str, RapidPVSTAttributes] | None = None


class SpanningTree(BaseModel):
    config: dict[str, SpanningTreeGlobalAttributes] | None = None  # SpanningTreeGlobalAttributes()
    rstp: RSTPConfig | None = RSTPConfig()
    mstp: MSTPConfig | None = MSTPConfig()
    rapidpvst: RapidPVSTConfig | None = RapidPVSTConfig()
