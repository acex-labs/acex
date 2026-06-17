from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

from acex_devkit.models.asset import (
    Asset as AssetSchema,
    AssetResponse,
    AssetClusterBase as AssetClusterSchema,
    AssetClusterCreate,
    AssetClusterUpdate,
    AssetClusterAssetResponse,
    AssetClusterResponse,
)


class Ned(SQLModel, table=True):
    name: str = Field(default="cisco_ios_ssh", primary_key=True)
    version: str = Field(default="0.0.1")


class AssetBase(AssetSchema, SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)


class AssetClusterLink(SQLModel, table=True):
    asset_id: int = Field(foreign_key="asset.id", primary_key=True)
    cluster_id: int = Field(foreign_key="assetcluster.id", primary_key=True)
    order: int = Field(default=0)


class Asset(AssetBase, table=True):
    clusters: list["AssetCluster"] = Relationship(
        back_populates="assets",
        link_model=AssetClusterLink
    )


class AssetClusterBase(AssetClusterSchema, SQLModel):
    pass


class AssetCluster(AssetClusterBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    assets: list[Asset] = Relationship(
        back_populates="clusters",
        link_model=AssetClusterLink
    )


__all__ = [
    "Ned",
    "AssetBase",
    "AssetClusterLink",
    "Asset",
    "AssetClusterBase",
    "AssetCluster",
    "AssetResponse",
    "AssetClusterCreate",
    "AssetClusterUpdate",
    "AssetClusterAssetResponse",
    "AssetClusterResponse",
]
