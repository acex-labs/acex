"""Declared hardware device types.

Importing this package registers every declaration, so the catalog below is
the single place to ask what hardware is selectable.
"""

from functools import cache

from acex_devkit.device_types import cisco as _cisco  # noqa: F401  (registers Cisco declarations)
from acex_devkit.device_types import fortinet as _fortinet  # noqa: F401  (registers Fortinet declarations)
from acex_devkit.device_types import juniper as _juniper  # noqa: F401  (registers Juniper declarations)
from acex_devkit.models.device_type import (
    DeviceType,
    InterfaceSlot,
    ModuleSlot,
    PortGroup,
    PortMedia,
    PortModule,
    Speed,
)
from acex_devkit.models.platform import OS, Vendor


@cache
def get(hardware_model: str) -> DeviceType | None:
    """Return the declared device type for a model string, or None."""
    klass = DeviceType.get(hardware_model)
    return klass() if klass is not None else None


@cache
def _all() -> tuple[DeviceType, ...]:
    return tuple(klass() for klass in dict.fromkeys(DeviceType.registry.values()))


def device_types(*, vendor: Vendor | None = None, os: OS | None = None) -> list[DeviceType]:
    """Every declared device type, optionally narrowed by vendor and/or OS."""
    return [d for d in _all() if (vendor is None or d.vendor == vendor) and (os is None or os in d.os)]


def models(*, vendor: Vendor | None = None, os: OS | None = None) -> list[str]:
    """Selectable hardware model strings, sorted. Use for API/UI options."""
    return sorted({m for d in device_types(vendor=vendor, os=os) for m in d.models})


def vendors() -> list[Vendor]:
    return sorted({d.vendor for d in _all()})


@cache
def get_module(model: str) -> PortModule | None:
    """Return the declared port module for a model string, or None."""
    klass = PortModule.get(model)
    return klass() if klass is not None else None


def port_modules(*, fits: str | None = None) -> list[str]:
    """Declared port module models, optionally only those fitting a device.

    Use for the per-slot module picker: ``port_modules(fits="C9300-24T")``.
    """
    known = sorted({m for klass in dict.fromkeys(PortModule.registry.values()) for m in klass().models})
    if fits is None:
        return known
    device = get(fits)
    if device is None or not device.slots:
        return []
    return [m for m in known if any(s.permits(m) for s in device.slots)]


__all__ = [
    "DeviceType",
    "InterfaceSlot",
    "ModuleSlot",
    "PortGroup",
    "PortMedia",
    "PortModule",
    "Speed",
    "device_types",
    "get",
    "get_module",
    "models",
    "port_modules",
    "vendors",
]
