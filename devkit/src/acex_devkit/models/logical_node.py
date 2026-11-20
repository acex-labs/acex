from typing import Any

from pydantic import BaseModel, Field

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.composed_configuration import ComposedConfiguration


class LogicalNodeBase(BaseModel):
    hostname: str = Field(default="R1")
    role: str = Field(default="core")
    site: str | None = Field(default=None)
    sequence: int | None = Field(default=None)


class LogicalNodeCreate(LogicalNodeBase):
    # What a caller of the client has to give. LogicalNodeBase also backs the table and the body of
    # the API's create and update routes, where a PATCH may leave the hostname out and the role
    # column is NOT NULL, so the stricter rules stay on this model.
    hostname: str
    role: str | None = None


class LogicalNodeUpdate(BaseModel):
    hostname: str | None = None
    role: str | None = None
    site: str | None = None
    sequence: int | None = None


class LogicalNodeListResponse(PersistedResponse, LogicalNodeBase):
    regions: list[str] = []


class LogicalNodeResponse(PersistedResponse, LogicalNodeBase):
    regions: list[str] = []


class LogicalNodeConfigResponse(PersistedResponse, LogicalNodeBase):
    configuration: ComposedConfiguration
    meta_data: dict[str, Any] = {}
    regions: list[str] = []
