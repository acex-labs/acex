"""Catalyst 6800 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class C6832_X_LE(CiscoIOSDevice):
    models: list[str] = ["C6832-X-LE"]
    ports: list[PortGroup] = [
        PortGroup(count=16, speeds=[Speed.gigabit, Speed.ten_gigabit]),
        PortGroup(count=16, speeds=[Speed.forty_gigabit]),
    ]


class C6880_X_LE(CiscoIOSDevice):
    models: list[str] = ["C6880-X-LE"]
    ports: list[PortGroup] = [PortGroup(count=80, speeds=[Speed.gigabit, Speed.ten_gigabit])]
