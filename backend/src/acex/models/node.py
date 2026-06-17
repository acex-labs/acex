from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from acex_devkit.models.node_response import (
    AssetRefType,
    NodeStatus,
    NodeResponse,
    NodeListItem as NodeListResponse,
)

if TYPE_CHECKING:
    from acex.models.logical_node import LogicalNode


class NodeBase(SQLModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType = AssetRefType.asset
    logical_node_id: int = Field(foreign_key="logicalnode.id")
    status: NodeStatus = Field(default=NodeStatus.planned)


class Node(NodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: Optional[datetime] = Field(default=None)
    logical_node: Optional["LogicalNode"] = Relationship(
        sa_relationship_kwargs={"lazy": "noload"}
    )


__all__ = [
    "Node",
    "NodeBase",
    "NodeStatus",
    "AssetRefType",
    "NodeResponse",
    "NodeListResponse",
]
