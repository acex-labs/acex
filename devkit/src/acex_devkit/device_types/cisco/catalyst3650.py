"""Catalyst 3650 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSXEDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C3650_24PD(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-24PD"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
    ]


class WS_C3650_24PDM(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-24PDM"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
    ]


class WS_C3650_24PS(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-24PS"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]


class WS_C3650_24TD(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-24TD"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]


class WS_C3650_48FQM(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-48FQM"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.forty_gigabit]),
    ]


class WS_C3650_48PD(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-48PD"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
    ]


class WS_C3650_48PQ(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-48PQ"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit]),
    ]


class WS_C3650_48PS(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-48PS"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]


class WS_C3650_48TQ(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-48TQ"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.forty_gigabit]),
    ]


class WS_C3650_48TS(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3650-48TS"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]
