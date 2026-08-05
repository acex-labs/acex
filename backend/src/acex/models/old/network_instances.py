from acex.models.attribute_value import AttributeValue
from sqlmodel import SQLModel


class NetworkInstanceAttributes(SQLModel):
    name: str = None
    vlans: dict | None = None


class L2DomainAttributes(NetworkInstanceAttributes): ...


class VlanAttributes(SQLModel):
    name: AttributeValue[str]
    vlan_id: AttributeValue[int] | None = None
    vlan_name: AttributeValue[str] | None = None
    network_instance: AttributeValue[str] | None = None
