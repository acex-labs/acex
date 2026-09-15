"""Catalyst 3560 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C3560CG_8PC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560CG-8PC-S"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=[Speed.gigabit])]


class WS_C3560CX_12PC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560CX-12PC-S"]
    ports: list[PortGroup] = [PortGroup(count=14, speeds=[Speed.gigabit])]


class WS_C3560CX_12PD_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560CX-12PD-S"]
    ports: list[PortGroup] = [PortGroup(count=14, speeds=[Speed.gigabit])]


class WS_C3560CX_8PC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560CX-8PC-S"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=[Speed.gigabit])]


class WS_C3560CX_8PT_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560CX-8PT-S"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=[Speed.gigabit])]


class WS_C3560CX_8TC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560CX-8TC-S"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=[Speed.gigabit])]


class WS_C3560C_12PC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560C-12PC-S"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C3560C_8PC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C3560C-8PC-S"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C3560G_24PS(CiscoIOSDevice):
    models: list[str] = ["WS-C3560G-24PS"]
    ports: list[PortGroup] = [PortGroup(count=26, speeds=[Speed.gigabit])]


class WS_C3560G_48PS(CiscoIOSDevice):
    models: list[str] = ["WS-C3560G-48PS"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C3560G_48TS(CiscoIOSDevice):
    models: list[str] = ["WS-C3560G-48TS"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C3560V2_24PS(CiscoIOSDevice):
    models: list[str] = ["WS-C3560V2-24PS"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C3560_24PS(CiscoIOSDevice):
    models: list[str] = ["WS-C3560-24PS"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C3560_24TS(CiscoIOSDevice):
    models: list[str] = ["WS-C3560-24TS"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C3560_8PC(CiscoIOSDevice):
    models: list[str] = ["WS-C3560-8PC"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
