from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from acex_devkit.models.asset import (
    AssetClusterResponse,
    AssetResponse,
)
from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.logical_node import LogicalNodeResponse


class AssetRefType(StrEnum):
    asset = "asset"
    asset_cluster = "asset_cluster"


class NodeStatus(StrEnum):
    planned = "planned"
    init = "init"
    active = "active"
    decommissioned = "decommissioned"


class NodeBase(BaseModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType | None = None
    logical_node_id: int
    status: NodeStatus | None = None


class NodeListItem(PersistedResponse, NodeBase):
    hostname: str | None = None
    site: str | None = None
    role: str | None = None
    regions: list[str] = []
    vendor: str | None = None
    os: str | None = None
    ned_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    asset_ref_id: int | None = None
    asset_ref_type: AssetRefType | None = None
    logical_node_id: int | None = None
    status: NodeStatus | None = None


class NodeResponse(PersistedResponse, NodeBase):
    asset: Annotated[AssetResponse | AssetClusterResponse, Field(discriminator="type")]
    logical_node: LogicalNodeResponse
    regions: list[str] = []
    created_at: datetime
    updated_at: datetime | None = None


__all__ = [
    "LogicalNodeResponse",
    "AssetRefType",
    "NodeStatus",
    "NodeBase",
    "NodeListItem",
    "NodeResponse",
]
