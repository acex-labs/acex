"""Catalyst 3500 XL / 3550 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C3524_XL(CiscoIOSDevice):
    models: list[str] = ["WS-C3524-XL"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C3550_12G(CiscoIOSDevice):
    models: list[str] = ["WS-C3550-12G"]
    ports: list[PortGroup] = [PortGroup(count=12, speeds=[Speed.gigabit])]
