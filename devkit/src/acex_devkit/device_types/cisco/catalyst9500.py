"""Catalyst 9500 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSXEDevice
from acex_devkit.models.device_type import PortGroup, Speed


class C9500_16X(CiscoIOSXEDevice):
    models: list[str] = ["C9500-16X"]
    ports: list[PortGroup] = [PortGroup(count=16, speeds=[Speed.gigabit, Speed.ten_gigabit])]


class C9500_24Y4C(CiscoIOSXEDevice):
    models: list[str] = ["C9500-24Y4C"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit]),
        PortGroup(count=4, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit]),
    ]


class C9500_40X(CiscoIOSXEDevice):
    models: list[str] = ["C9500-40X"]
    ports: list[PortGroup] = [PortGroup(count=40, speeds=[Speed.gigabit, Speed.ten_gigabit])]


class C9500_48Y4C(CiscoIOSXEDevice):
    models: list[str] = ["C9500-48Y4C"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit]),
        PortGroup(count=4, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit]),
    ]
