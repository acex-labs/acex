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

class VlanMap(SQLModel):
    vlans: Optional[dict] = None


class VlanMapAttributes(SQLModel):
    name: str
    vlans: Optional[dict|list] = None