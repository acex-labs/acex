from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from acex_devkit.models.node_response import (
    AssetRefType,
    NodeAdminStatus,
    NodeInstance,
    NodeProvisionStatus,
)
from acex_devkit.models.node_response import (
    NodeListItem as NodeListResponse,
)
from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from acex.models.logical_node import LogicalNode
    from acex.models.management_connections import ManagementConnection


class NodeBase(SQLModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType = AssetRefType.asset
    logical_node_id: int = Field(foreign_key="logicalnode.id")
    admin_status: NodeAdminStatus = Field(default=NodeAdminStatus.planned)
    provision_status: NodeProvisionStatus = Field(default=NodeProvisionStatus.unprovisioned)


class Node(NodeBase, table=True):
    # One node instance per logical node and per asset or cluster. Created by a migration only when the data is clean.
    __table_args__ = (
        Index("uq_node_logical_node_id", "logical_node_id", unique=True),
        Index("uq_node_asset_ref", "asset_ref_type", "asset_ref_id", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    #: The provision_status the node had when it was enrolled in ZTP; it returns
    #: to it if ZTP is cancelled. None while the node is not in ZTP.
    ztp_previous_status: NodeProvisionStatus | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime | None = Field(default=None)
    logical_node: Optional["LogicalNode"] = Relationship(sa_relationship_kwargs={"lazy": "noload"})
    management_connections: list["ManagementConnection"] = Relationship(sa_relationship_kwargs={"lazy": "noload"})


__all__ = [
    "Node",
    "NodeBase",
    "NodeAdminStatus",
    "NodeProvisionStatus",
    "AssetRefType",
    "NodeInstance",
    "NodeListResponse",
]
