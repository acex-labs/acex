"""Catalyst 2950 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C2950G_24_EI(CiscoIOSDevice):
    models: list[str] = ["WS-C2950G-24-EI"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
    stackable: bool = False


class WS_C2950G_24_EI_DC(CiscoIOSDevice):
    models: list[str] = ["WS-C2950G-24-EI-DC"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
    stackable: bool = False


class WS_C2950G_48_EI(CiscoIOSDevice):
    models: list[str] = ["WS-C2950G-48-EI"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
    stackable: bool = False


class WS_C2950SX_48_SI(CiscoIOSDevice):
    models: list[str] = ["WS-C2950SX-48-SI"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
    stackable: bool = False


class WS_C2950T_24(CiscoIOSDevice):
    models: list[str] = ["WS-C2950T-24"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
    stackable: bool = False


class WS_C2950_24(CiscoIOSDevice):
    models: list[str] = ["WS-C2950-24"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.fast_ethernet])]
    stackable: bool = False
