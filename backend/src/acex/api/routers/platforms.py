"""Supported platform catalog.

What a client needs to fill in an asset form, in the order the form asks for
it: which vendors we have hardware declarations for, which hardware models
each one makes, and which OS a given model can run. Version examples are keyed
by OS, since they do not vary by model.

Everything here is derived from the devkit declarations - adding a device type
or a version scheme shows up in this endpoint with no change on this side.
"""

from acex.constants import BASE_URL
from acex_devkit import device_types as catalog
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor
from fastapi import APIRouter
from pydantic import BaseModel


class PlatformModel(BaseModel):
    """One hardware model and the operating systems it can run.

    Almost every model runs exactly one OS, so a client that has the model can
    usually settle the OS without asking.
    """

    hardware_model: str
    operating_systems: list[OS]


class PlatformVendor(BaseModel):
    """One supported vendor and the hardware declared under it."""

    vendor: Vendor
    hardware_models: list[PlatformModel]


class PlatformCatalog(BaseModel):
    vendors: list[PlatformVendor]
    version_examples: dict[OS, list[str]] = {}


def list_platforms() -> PlatformCatalog:
    """Vendors, hardware models and operating systems we have declarations for."""
    vendors = []
    for vendor in catalog.vendors():
        by_model: dict[str, set[OS]] = {}
        for device in catalog.device_types(vendor=vendor):
            for model in device.models:
                by_model.setdefault(model, set()).update(device.os)
        vendors.append(
            PlatformVendor(
                vendor=vendor,
                hardware_models=[
                    PlatformModel(hardware_model=model, operating_systems=sorted(os))
                    for model, os in sorted(by_model.items())
                ],
            )
        )

    examples = {}
    for os in OS:
        scheme = OsVersionScheme.for_os(os)
        if scheme and scheme.examples:
            examples[os] = scheme.examples

    return PlatformCatalog(vendors=vendors, version_examples=examples)


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/platforms")
    tags = ["Inventory"]
    router.add_api_route("", list_platforms, methods=["GET"], tags=tags, response_model=PlatformCatalog)
    return router
