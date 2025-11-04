from sqlmodel import SQLModel, Field
from typing import Optional, Dict
from enum import Enum

class ConnectionType(Enum):
    ssh = "ssh"
    telnet = "telnet"

class ManagementConnectionBase(SQLModel):
    primary: bool = True
    node_id: int
    connection_type: ConnectionType = Field(default=ConnectionType.ssh)
    target_ip: Optional[str] = None

class ManagementConnection(ManagementConnectionBase, table=True):
    __tablename__ = "mgmt_connection"
    id: int = Field(primary_key=True)

class ManagementConnectionResponse(ManagementConnection):
    id: int

class DeviceManagement(SQLModel):
    asset_id: int
    logical_node_id: int

