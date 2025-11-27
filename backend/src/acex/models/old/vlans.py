from sqlmodel import SQLModel, Field
from typing import Any

class VlanAttributes(SQLModel):
    name: str = None
    vlan_id: int = None
    vlan_name: str = False