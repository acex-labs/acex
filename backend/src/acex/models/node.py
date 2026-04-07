from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, TYPE_CHECKING
from enum import Enum
from datetime import datetime

from acex.models import LogicalNodeResponse
from acex.models import AssetResponse

if TYPE_CHECKING:
    from acex.models.logical_node import LogicalNode


class AssetRefType(str, Enum):
    asset = "asset"
    assetcluster = "assetcluster"


class NodeStatus(str, Enum):
    planned = "planned"
    init = "init"
    active = "active"
    decommissioned = "decommissioned"


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

class NodeListResponse(NodeBase):
    id: int
    hostname: Optional[str] = None
    site: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class NodeResponse(NodeBase):
    asset: AssetResponse
    logical_node: LogicalNodeResponse
    created_at: datetime
    updated_at: Optional[datetime] = None
