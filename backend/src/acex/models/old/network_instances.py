from sqlmodel import SQLModel, Field
from typing import Any, Optional
from acex.models.attribute_value import AttributeValue

class NetworkInstanceAttributes(SQLModel):
    name: str = None
    vlans: Optional[dict] = None


class L2DomainAttributes(NetworkInstanceAttributes):... 


class VlanAttributes(SQLModel):
    name: AttributeValue[str]
    vlan_id: Optional[AttributeValue[int]] = None
    vlan_name: Optional[AttributeValue[str]] = None
    network_instance: Optional[AttributeValue[str]] = None
