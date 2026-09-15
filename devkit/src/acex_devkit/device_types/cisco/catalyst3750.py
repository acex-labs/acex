"""Catalyst 3750 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C3750G_12S(CiscoIOSDevice):
    models: list[str] = ["WS-C3750G-12S"]
    ports: list[PortGroup] = [PortGroup(count=12, speeds=[Speed.gigabit])]


class WS_C3750G_12S_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3750G-12S-S"]
    ports: list[PortGroup] = [PortGroup(count=12, speeds=[Speed.gigabit])]


class WS_C3750G_24TS_1U(CiscoIOSDevice):
    models: list[str] = ["WS-C3750G-24TS-1U"]
    ports: list[PortGroup] = [PortGroup(count=26, speeds=[Speed.gigabit])]


class WS_C3750G_48TS(CiscoIOSDevice):
    models: list[str] = ["WS-C3750G-48TS"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C3750X_24(CiscoIOSDevice):
    models: list[str] = ["WS-C3750X-24"]
    ports: list[PortGroup] = [PortGroup(count=26, speeds=[Speed.gigabit])]


class WS_C3750X_24P(CiscoIOSDevice):
    models: list[str] = ["WS-C3750X-24P"]
    ports: list[PortGroup] = [PortGroup(count=26, speeds=[Speed.gigabit])]
