from sqlmodel import SQLModel, Field
from typing import Any, Optional

class Network(SQLModel): ...

class InterfacesAttributes(SQLModel):
    name: str = None
    interface: str = None
    id: str = None

class VlansAttributes(SQLModel):
    vlan_id: int = None
    vlan_name: str = None
    name: str = None
    #name: Optional[int] = Field(default=None)
#
    #def __init__(self, **data):
    #    super().__init__(**data)
    #    if self.name is None:
    #        self.name = self.vlan_id


#class Global(Interfaces):
#    name: str = 'GLOBAL'
#    vlans = Vlans
#    interfaces = Interfaces

#class L2vsiInstance(NetworkInstance):
#    interface: str = None
#    vlan: str = None
#
#class L3VrfInstance(NetworkInstance):
#    name: str = None # te0/12/116.2048
#    interface: str = None # te0/12/116
#    subinterface: id = 2048
