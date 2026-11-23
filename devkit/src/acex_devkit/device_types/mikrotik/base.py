"""MikroTik device base class.

RouterOS names Ethernet ports ``ether1``..``etherN`` and gives each cage its own name (``sfp1``, ``sfp-sfpplus1``),
which is the driver's concern. A device is one box: RouterBOARDs do not stack.
"""

from acex_devkit.models.device_type import DeviceType
from acex_devkit.models.platform import OS, Vendor


class MikroTikDevice(DeviceType, abstract=True):
    """A MikroTik RouterBOARD running RouterOS."""

    vendor: Vendor = Vendor.mikrotik
    os: list[OS] = [OS.mikrotik_routeros]
    stackable: bool = False
