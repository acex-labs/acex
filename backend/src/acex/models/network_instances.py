from sqlmodel import SQLModel, Field
from typing import Any, Optional



class NetworkInstanceAttributes(SQLModel):
    name: str = None
    vlans: Optional[dict] = None


class L2DomainAttributes(NetworkInstanceAttributes):... 


class VlanAttributes(SQLModel):
    name: str = None
    vlan_id: int = None
    vlan_name: str = None
