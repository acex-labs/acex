from pydantic import BaseModel, Field
from typing import Annotated, Optional, Union
from enum import Enum
from datetime import datetime

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.logical_node import LogicalNodeResponse
from acex_devkit.models.asset import Asset, AssetClusterBase, AssetClusterAssetResponse, AssetResponse, AssetClusterResponse


class AssetRefType(str, Enum):
    asset = "asset"
    asset_cluster = "asset_cluster"


class NodeStatus(str, Enum):
    planned = "planned"
    init = "init"
    active = "active"
    decommissioned = "decommissioned"


class NodeBase(BaseModel):
    asset_ref_id: int
    asset_ref_type: Optional[AssetRefType] = None
    logical_node_id: int
    status: Optional[NodeStatus] = None


class NodeListItem(PersistedResponse, NodeBase):
    hostname: Optional[str] = None
    site: Optional[str] = None
    role: Optional[str] = None
    regions: list[str] = []
    vendor: Optional[str] = None
    os: Optional[str] = None
    ned_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NodeResponse(PersistedResponse, NodeBase):
    asset: Annotated[Union[AssetResponse, AssetClusterResponse], Field(discriminator="type")]
    logical_node: LogicalNodeResponse
    regions: list[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


__all__ = [
    "LogicalNodeResponse",
    "AssetRefType",
    "NodeStatus",
    "NodeBase",
    "NodeListItem",
    "NodeResponse",
]
