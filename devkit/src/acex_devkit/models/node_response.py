from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from acex_devkit.models.composed_configuration import ComposedConfiguration


class LogicalNodeResponse(BaseModel):
    id: Optional[int] = Field(None, title='Id')
    hostname: Optional[str] = Field('R1', title='Hostname')
    role: Optional[str] = Field('core', title='Role')
    site: Optional[str] = Field('HQ', title='Site')
    sequence: Optional[int] = Field(1, title='Sequence')
    configuration: Optional[ComposedConfiguration] = ComposedConfiguration()
    meta_data: Optional[Dict[str, Any]] = Field(None, title='Meta Data')


class Asset(BaseModel):
    id: Optional[int] = None
    vendor: str = None
    serial_number: str
    os: str
    os_version: str
    hardware_model: str
    ned_id: Optional[str] = None


class AssetRefType(str, Enum):
    asset = "asset"
    assetcluster = "assetcluster"


class NodeBase(BaseModel):
    asset_ref_id: int
    asset_ref_type: AssetRefType = AssetRefType.asset
    logical_node_id: int

class Node(NodeBase):
    id: Optional[int] = None

class NodeResponse(NodeBase):
    asset: Asset
    logical_node: LogicalNodeResponse
