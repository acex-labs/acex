from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from acex_devkit.models.base import PersistedResponse


class OS(StrEnum):
    arista_eos = "arista_eos"
    cisco_ios = "cisco_ios"
    cisco_iosxe = "cisco_iosxe"
    cisco_iosxr = "cisco_iosxr"
    cisco_nxos = "cisco_nxos"
    fortinet_fortios = "fortinet_fortios"
    juniper_junos = "juniper_junos"


class Vendor(StrEnum):
    arista = "arista"
    cisco = "cisco"
    Cisco = "Cisco"
    fortinet = "fortinet"
    juniper = "juniper"


class Asset(BaseModel):
    vendor: Vendor = Field(default=Vendor.cisco)
    serial_number: str = Field(default="abc123")
    os: OS = Field(default=OS.cisco_ios)
    os_version: str = Field(default="12.0.1")
    hardware_model: str = Field(default="")
    ned_id: str | None = None


class AssetCreate(Asset):
    pass


class AssetUpdate(BaseModel):
    vendor: Vendor | None = None
    serial_number: str | None = None
    os: OS | None = None
    os_version: str | None = None
    hardware_model: str | None = None
    ned_id: str | None = None


class AssetResponse(PersistedResponse, Asset):
    type: Literal["asset"] = "asset"


class AssetClusterBase(BaseModel):
    name: str
    ned_id: str | None = None


class AssetClusterCreate(AssetClusterBase):
    asset_ids: list[int] = []


class AssetClusterUpdate(BaseModel):
    name: str | None = None
    ned_id: str | None = None
    asset_ids: list[int] | None = None


class AssetClusterAssetResponse(PersistedResponse, Asset):
    cluster_index: int | None = None


class AssetClusterResponse(PersistedResponse, AssetClusterBase):
    type: Literal["asset_cluster"] = "asset_cluster"
    assets: list[AssetClusterAssetResponse] = []
