from acex_devkit.models.logical_node import (
    LogicalNodeBase as LogicalNodeSchema,
)
from acex_devkit.models.logical_node import (
    LogicalNodeConfigResponse,
    LogicalNodeCreate,
    LogicalNodeListResponse,
    LogicalNodeResponse,
)
from sqlmodel import Field, SQLModel


class LogicalNodeBase(LogicalNodeSchema, SQLModel):
    pass


class LogicalNode(LogicalNodeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


__all__ = [
    "LogicalNode",
    "LogicalNodeBase",
    "LogicalNodeCreate",
    "LogicalNodeListResponse",
    "LogicalNodeResponse",
    "LogicalNodeConfigResponse",
]
