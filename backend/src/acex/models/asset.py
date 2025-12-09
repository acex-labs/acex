from typing import Optional, Dict, List
from sqlmodel import SQLModel, Field, Relationship


class Ned(SQLModel, table=True):
    name: str = Field(default="cisco_ios_ssh", primary_key=True)
    version: str = Field(default="0.0.1")


class AssetBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    vendor: str = Field(default="cisco")
    serial_number: str = Field(default="abc123")
    os: str = Field(default="ios")
    os_version: str = Field(default="12.0.1")
    hardware_model: str = Field(default="")
    ned_id: Optional[str] = None


class AssetClusterLink(SQLModel, table=True):
    asset_id: int = Field(foreign_key="asset.id", primary_key=True)
    cluster_id: int = Field(foreign_key="assetcluster.id", primary_key=True)
    order: int = Field(default=0)


class Asset(AssetBase, table=True):
    clusters: list["AssetCluster"] = Relationship(
        back_populates="assets",
        link_model=AssetClusterLink
    )


class AssetClusterBase(SQLModel):
    name: str

class AssetClusterCreate(AssetClusterBase):
    pass


class AssetCluster(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

    assets: list[Asset] = Relationship(
        back_populates="clusters",
        link_model=AssetClusterLink
    )


class AssetResponse(AssetBase):
    meta_data: Dict = Field(default_factory=dict)
