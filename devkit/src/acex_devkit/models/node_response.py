from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
from acex_devkit.models.composed_configuration import ComposedConfiguration


class LogicalNodeResponse(BaseModel):
    id: Optional[int] = None
    hostname: Optional[str] = None
    role: Optional[str] = None
    site: Optional[str] = None
    sequence: Optional[int] = None
    configuration: Optional[ComposedConfiguration] = None
    meta_data: Optional[Dict[str, Any]] = None


class Asset(BaseModel):
    id: Optional[int] = None
    vendor: Optional[str] = None
    serial_number: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    hardware_model: Optional[str] = None
    ned_id: Optional[str] = None


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

class Node(NodeBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NodeListItem(NodeBase):
    """Enriched list representation with denormalized fields from asset and logical_node."""
    id: Optional[int] = None
    # From logical_node
    hostname: Optional[str] = None
    site: Optional[str] = None
    # From asset
    vendor: Optional[str] = None
    os: Optional[str] = None
    ned_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NodeResponse(NodeBase):
    id: Optional[int] = None
    asset: Asset
    logical_node: LogicalNodeResponse
    created_at: datetime
    updated_at: Optional[datetime] = None
