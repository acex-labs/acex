"""Waystream device base class.

iBOS names Ethernet ports ``gigabitethernetN`` and ``tengigabitethernetN`` on the MS4000 and ASR6000 and
``ethernetS/P`` on the MS 7000, which is the driver's concern. The names carry no stack number, so a device is one box.
"""

from acex_devkit.models.device_type import DeviceType
from acex_devkit.models.platform import OS, Vendor


class WaystreamDevice(DeviceType, abstract=True):
    """A Waystream switch running iBOS."""

    vendor: Vendor = Vendor.waystream
    os: list[OS] = [OS.waystream_ibos]
    stackable: bool = False
