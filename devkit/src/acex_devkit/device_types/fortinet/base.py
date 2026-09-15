"""Fortinet device base classes.

FortiOS numbers front-panel interfaces ``port1``..``portN`` in one continuous
run, regardless of whether a position is RJ-45 or a fibre cage - so the media
on each port group is the only thing that tells them apart. FortiGates do not
stack; HA clustering does not renumber ports.
"""

from acex_devkit.models.asset import OS, Vendor
from acex_devkit.models.device_type import DeviceType


class FortiGateDevice(DeviceType, abstract=True):
    """Fortinet FortiGate firewall running FortiOS."""

    vendor: Vendor = Vendor.fortinet
    os: list[OS] = [OS.fortinet_fortios]
    stackable: bool = False
