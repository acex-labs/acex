"""Cisco device and module base classes.

Vendor and OS identity live here so a device declaration only has to state
its model strings and its ports.
"""

from acex_devkit.models.device_type import DeviceType, PortModule
from acex_devkit.models.platform import OS, Vendor


class CiscoIOSDevice(DeviceType, abstract=True):
    """Cisco device running cisco_ios."""

    vendor: Vendor = Vendor.cisco
    os: list[OS] = [OS.cisco_ios]


class CiscoIOSXEDevice(DeviceType, abstract=True):
    """Cisco device running cisco_iosxe."""

    vendor: Vendor = Vendor.cisco
    os: list[OS] = [OS.cisco_iosxe]


class CiscoNXOSDevice(DeviceType, abstract=True):
    """Cisco device running cisco_nxos."""

    vendor: Vendor = Vendor.cisco
    os: list[OS] = [OS.cisco_nxos]


class CiscoNetworkModule(PortModule, abstract=True):
    """Base for Catalyst network modules (C9x00-NM-*)."""
