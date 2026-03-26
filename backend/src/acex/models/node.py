from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, TYPE_CHECKING
from enum import Enum

from acex.models import LogicalNodeResponse
from acex.models import AssetResponse

if TYPE_CHECKING:
    from acex.models.logical_node import LogicalNode


class AssetRefType(str, Enum):
    asset = "asset"
    assetcluster = "assetcluster"


class NodeBase(SQLModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType = AssetRefType.asset
    logical_node_id: int = Field(foreign_key="logicalnode.id")

class Node(NodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    logical_node: Optional["LogicalNode"] = Relationship(
        sa_relationship_kwargs={"lazy": "noload"}
    )

class NodeListResponse(NodeBase):
    id: int
    hostname: Optional[str] = None
    site: Optional[str] = None

class NodeResponse(NodeBase):
    asset: AssetResponse
    logical_node: LogicalNodeResponse
