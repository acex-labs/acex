"""Catalyst 3850 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSXEDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C3850_12S(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-12S"]
    ports: list[PortGroup] = [PortGroup(count=12, speeds=[Speed.gigabit])]


class WS_C3850_12XS(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-12XS"]
    ports: list[PortGroup] = [PortGroup(count=12, speeds=[Speed.gigabit, Speed.ten_gigabit])]


class WS_C3850_24S(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-24S"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]


class WS_C3850_24T(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]


class WS_C3850_24XS(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-24XS"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit, Speed.ten_gigabit])]


class WS_C3850_48P(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]


class WS_C3850_48T(CiscoIOSXEDevice):
    models: list[str] = ["WS-C3850-48T"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]
