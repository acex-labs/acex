from sqlmodel import SQLModel


class VlanAttributes(SQLModel):
    name: str = None
    vlan_id: int = None
    vlan_name: str = False
