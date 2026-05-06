from sqlalchemy import Column, ForeignKey, Integer
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
    node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

class ManagementConnectionResponse(ManagementConnection):
    pass

class DeviceManagement(SQLModel):
    asset_id: int
    logical_node_id: int

