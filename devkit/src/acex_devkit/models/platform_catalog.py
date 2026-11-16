"""The hardware ACEX can work with, in three layers.

The devkit declarations are the base: every vendor, hardware model and OS we know. Of those, the installed NEDs
support some, and of the supported ones an administrator enables the models the installation actually runs.
"""

from pydantic import BaseModel

from acex_devkit.models.platform import OS, Vendor


class PlatformModel(BaseModel):
    """One hardware model and the operating systems it can run.

    Almost every model runs exactly one OS, so a client that has the model can usually settle the OS without
    asking.
    """

    hardware_model: str
    operating_systems: list[OS]
    #: The operating systems on this model that an installed NED supports.
    supported_os: list[OS] = []
    #: Enabled by an administrator, or by an asset of this model entering the inventory.
    enabled: bool = False


class PlatformVendor(BaseModel):
    """One vendor and the hardware declared under it."""

    vendor: Vendor
    hardware_models: list[PlatformModel]


class PlatformCatalog(BaseModel):
    vendors: list[PlatformVendor]
    version_examples: dict[OS, list[str]] = {}
