"""Policies: what the environment should look like, set by an administrator and measured by compliance.

A policy holds for the whole installation. Each type is its own model.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

from acex_devkit import device_types, os_versions  # noqa: F401  (registers the declarations checked below)
from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor


class SoftwarePolicyBase(BaseModel):
    """A software version approved for a vendor's devices, or for one hardware model of it. A version not
    approved is not allowed; the golden one is the version to aim for."""

    vendor: Vendor
    #: None for every model of the vendor; a model's own versions beat the vendor's.
    hardware_model: str | None = None
    os: OS
    os_version: str
    #: At most one golden version per vendor and hardware model; the others are accepted.
    golden: bool = False


class SoftwarePolicyCreate(SoftwarePolicyBase):
    @field_validator("hardware_model")
    @classmethod
    def _model_or_none(cls, value: str | None) -> str | None:
        """None for blank; a declared model spelled as the devkit declares it."""
        value = (value or "").strip() or None
        device = device_types.get(value) if value else None
        if device is None:
            return value
        return next(m for m in device.models if m.casefold() == value.casefold())

    @model_validator(mode="after")
    def _check(self):
        """The OS is one the hardware runs, and the version one that OS can report."""
        runs = self.runnable_os()
        if runs and self.os not in runs:
            where = self.hardware_model or self.vendor.value
            raise ValueError(f"{where} does not run {self.os.value}; it runs {', '.join(sorted(runs))}")
        scheme = OsVersionScheme.for_os(self.os)
        if scheme is None:
            raise ValueError(f"no version scheme declared for {self.os.value}")
        self.os_version = scheme.check(self.os_version)
        return self

    def runnable_os(self) -> set[OS]:
        """The OSes the declared hardware runs: the model's when it is declared, else the vendor's.
        Empty when nothing is declared, and then any OS is allowed."""
        device = device_types.get(self.hardware_model) if self.hardware_model else None
        if device is not None:
            if device.vendor != self.vendor:
                raise ValueError(f"{self.hardware_model} is made by {device.vendor.value}, not {self.vendor.value}")
            return set(device.os)
        return {os for d in device_types.device_types(vendor=self.vendor) for os in d.os}

    @staticmethod
    def version_key(os: OS, version: str):
        """Spellings of the same version compare equal where the OS's scheme can tell."""
        scheme = OsVersionScheme.for_os(OS(os))
        return (scheme.normalize(version) if scheme and scheme.accepts(version) else None) or version


class SoftwarePolicyUpdate(BaseModel):
    """Change an approved version. Only the fields sent change; hardware_model None makes it the vendor's."""

    vendor: Vendor | None = None
    hardware_model: str | None = None
    os: OS | None = None
    os_version: str | None = None
    golden: bool | None = None


class SoftwareVersionInUse(BaseModel):
    """A version assets in the inventory report, and how many of them: a suggestion for what to approve."""

    os_version: str
    assets: int


class SoftwarePolicyResponse(PersistedResponse, SoftwarePolicyBase):
    updated_by: str | None = None
    updated_at: datetime | None = None
