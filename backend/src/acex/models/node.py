from sqlmodel import SQLModel, Field
from typing import Optional, Dict
from enum import Enum

from acex.models import LogicalNodeResponse
from acex.models import AssetResponse


class AssetRefType(str, Enum):
    asset = "asset"
    assetcluster = "assetcluster"


class NodeBase(SQLModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType = AssetRefType.asset
    logical_node_id: int

class Node(NodeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

class NodeResponse(NodeBase):
    asset: AssetResponse
    logical_node: LogicalNodeResponse
