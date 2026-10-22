from pydantic import BaseModel, model_validator

from acex_devkit import device_types
from acex_devkit.models.asset import Asset
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import StateKind


class Ned(BaseModel):
    name: str
    package_name: str
    version: str
    description: str
    filename: str


class Platform(BaseModel):
    """A platform a NED declares support for. Versions and models are checked against devkit."""

    vendor: Vendor
    os: OS
    os_versions: list[str] | None = None  # None = every version
    hardware_models: list[str] | None = None  # None = every model

    @model_validator(mode="after")
    def _check_against_devkit(self):
        scheme = OsVersionScheme.for_os(self.os)
        for version in self.os_versions or ():
            scheme.check(version)
        for model in self.hardware_models or ():
            if device_types.get(model) is None:
                raise ValueError(f"{model!r} is not a declared device type")
        return self

    def matches(self, asset: Asset) -> bool:
        if (asset.vendor, asset.os) != (self.vendor, self.os):
            return False
        if self.hardware_models is not None and asset.hardware_model not in self.hardware_models:
            return False
        if self.os_versions is None:
            return True
        if asset.os_version is None:
            return False
        scheme = OsVersionScheme.for_os(self.os)
        version = scheme.normalize(asset.os_version) or asset.os_version
        return any((scheme.normalize(v) or v) == version for v in self.os_versions)


class Capabilities(BaseModel):
    """What a NED supports. Platforms are declared; everything else is detected from the code."""

    platforms: list[Platform] = []
    configuration: list[str] = []  # components covered by the codec's mapper
    operations: list[str] = []  # transport operations: get_config, apply, execute
    state: list[StateKind] = []
    actions: list[str] = []
