from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ConnectionType(str, Enum):
    ssh = "ssh"
    telnet = "telnet"


class ManagementConnection(BaseModel):
    id: Optional[int] = None
    node_id: Optional[int] = None
    primary: bool = True
    connection_type: ConnectionType = ConnectionType.ssh
    target_ip: Optional[str] = None
