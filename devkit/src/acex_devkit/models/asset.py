from typing import Literal

from pydantic import BaseModel, model_validator

from acex_devkit import os_versions  # noqa: F401  (registers the version schemes)
from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor


class Asset(BaseModel):
    vendor: Vendor
    serial_number: str
    os: OS
    hardware_model: str

    # Read off the device, so genuinely unknown until the asset is discovered.
    os_version: str | None = None
    ned_id: str | None = None

    @model_validator(mode="after")
    def _check_os_version(self):
        """Check ``os_version`` against the scheme declared for this asset's ``os``.

        An asset that has not been discovered yet has no version, which is why
        the field is optional. A version that *is* given must be checkable:
        every OS is required to declare a scheme, and ``test_os_versions``
        holds us to it.
        """
        if self.os_version is None:
            return self
        scheme = OsVersionScheme.for_os(self.os)
        if scheme is None:
            raise ValueError(f"no version scheme declared for {self.os.value}")
        self.os_version = scheme.check(self.os_version)
        return self


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
