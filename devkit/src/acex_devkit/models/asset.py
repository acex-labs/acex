from typing import Literal

from pydantic import BaseModel, Field

from acex_devkit.models.base import PersistedResponse


class Asset(BaseModel):
    vendor: str = Field(default="cisco")
    serial_number: str = Field(default="abc123")
    os: str = Field(default="ios")
    os_version: str = Field(default="12.0.1")
    hardware_model: str = Field(default="")
    ned_id: str | None = None


class AssetResponse(PersistedResponse, Asset):
    type: Literal["asset"] = "asset"


class AssetClusterBase(BaseModel):
    name: str
    ned_id: str | None = None


class AssetClusterCreate(AssetClusterBase):
    pass


class AssetClusterUpdate(BaseModel):
    name: str | None = None
    ned_id: str | None = None
    asset_ids: list[int] | None = None


class AssetClusterAssetResponse(PersistedResponse, Asset):
    cluster_index: int | None = None


class AssetClusterResponse(PersistedResponse, AssetClusterBase):
    type: Literal["asset_cluster"] = "asset_cluster"
    assets: list[AssetClusterAssetResponse] = []
