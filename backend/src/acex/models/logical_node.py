from acex.utils.identity import key_expr
from acex_devkit.models.logical_node import (
    LogicalNodeBase as LogicalNodeSchema,
)
from acex_devkit.models.logical_node import (
    LogicalNodeConfigResponse,
    LogicalNodeCreate,
    LogicalNodeListResponse,
    LogicalNodeResponse,
)
from sqlalchemy import Index, column
from sqlmodel import Field, SQLModel


class LogicalNodeBase(LogicalNodeSchema, SQLModel):
    pass


class LogicalNode(LogicalNodeBase, table=True):
    # Unique hostname, ignoring case and padding. Created by a migration only when the data is clean.
    __table_args__ = (Index("uq_logicalnode_hostname_norm", key_expr(column("hostname")), unique=True),)

    id: int | None = Field(default=None, primary_key=True)


__all__ = [
    "LogicalNode",
    "LogicalNodeBase",
    "LogicalNodeCreate",
    "LogicalNodeListResponse",
    "LogicalNodeResponse",
    "LogicalNodeConfigResponse",
]
