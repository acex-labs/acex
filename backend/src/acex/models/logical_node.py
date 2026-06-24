from sqlmodel import SQLModel, Field
from typing import Optional

from acex_devkit.models.logical_node import (
    LogicalNodeBase as LogicalNodeSchema,
    LogicalNodeCreate,
    LogicalNodeListResponse,
    LogicalNodeResponse,
    LogicalNodeConfigResponse,
)


class LogicalNodeBase(LogicalNodeSchema, SQLModel):
    pass


class LogicalNode(LogicalNodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


__all__ = [
    "LogicalNode",
    "LogicalNodeBase",
    "LogicalNodeCreate",
    "LogicalNodeListResponse",
    "LogicalNodeResponse",
    "LogicalNodeConfigResponse",
]
