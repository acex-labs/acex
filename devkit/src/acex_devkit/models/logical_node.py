from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.composed_configuration import ComposedConfiguration


class LogicalNodeBase(BaseModel):
    hostname: str = Field(default="R1")
    role: str = Field(default="core")
    site: Optional[str] = Field(default=None)
    sequence: Optional[int] = Field(default=None)


class LogicalNodeCreate(LogicalNodeBase):
    pass


class LogicalNodeListResponse(PersistedResponse, LogicalNodeBase):
    regions: list[str] = []


class LogicalNodeResponse(PersistedResponse, LogicalNodeBase):
    regions: list[str] = []


class LogicalNodeConfigResponse(PersistedResponse, LogicalNodeBase):
    configuration: ComposedConfiguration
    meta_data: Dict[str, Any] = {}
    regions: list[str] = []
