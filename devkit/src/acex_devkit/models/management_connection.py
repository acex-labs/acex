from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class ConnectionType(StrEnum):
    ssh = "ssh"
    telnet = "telnet"


class ManagementConnectionBase(BaseModel):
    primary: bool = True
    connection_type: ConnectionType = ConnectionType.ssh
    target_ip: str | None = None


class ManagementConnectionCreate(ManagementConnectionBase):
    pass


class ManagementConnectionUpdate(BaseModel):
    primary: bool | None = None
    connection_type: ConnectionType | None = None
    target_ip: str | None = None


class ManagementConnectionResponse(PersistedResponse, ManagementConnectionBase):
    node_id: int


# Kept for backward compatibility
ManagementConnection = ManagementConnectionResponse
