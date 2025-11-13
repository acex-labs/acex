from sqlmodel import SQLModel, Field
from typing import Any, Optional



class NetworkInstanceAttributes(SQLModel):
    name: str = None


class VlanAttributes(SQLModel):
    name: str = None
    vlan_id: int = None
    vlan_name: str = None


class L2DomainAttributes(SQLModel): 
    name: str = None

class L2DomainL2VlanCompositionAttributes(NetworkInstanceAttributes):
    name: str
    vlan_id: int
    vlan_name: Optional[str] = None
    vlans: Optional[dict] = None

