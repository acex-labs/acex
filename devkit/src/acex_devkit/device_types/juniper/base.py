"""Juniper device and module base classes.

Junos names front-panel ports ``<medium>-<fpc>/<pic>/<port>`` - all three
indices zero-based. ``fpc`` is the Virtual Chassis member, ``pic`` the port
group on that member, so uplinks and extension modules land on pic 1 and up.
Rendering that name is the driver's job; this package declares the hardware.
"""

from acex_devkit.models.asset import OS, Vendor
from acex_devkit.models.device_type import DeviceType, PortModule


class JuniperEXDevice(DeviceType, abstract=True):
    """Juniper EX series switch running Junos."""

    vendor: Vendor = Vendor.juniper
    os: list[OS] = [OS.juniper_junos]


class JuniperExtensionModule(PortModule, abstract=True):
    """Base for EX extension modules (EX4400-EM-*)."""
