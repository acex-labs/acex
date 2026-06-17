from pydantic import BaseModel
from typing import Optional
from enum import Enum

from acex_devkit.models.base import PersistedResponse


class ConnectionType(str, Enum):
    ssh = "ssh"
    telnet = "telnet"


class ManagementConnectionBase(BaseModel):
    primary: bool = True
    connection_type: ConnectionType = ConnectionType.ssh
    target_ip: Optional[str] = None


class ManagementConnectionResponse(PersistedResponse, ManagementConnectionBase):
    node_id: int


# Kept for backward compatibility
ManagementConnection = ManagementConnectionResponse
