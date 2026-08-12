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
    pass


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
