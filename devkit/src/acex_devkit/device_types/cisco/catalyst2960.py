"""Catalyst 2960 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class WS_C2960CPD_8TT_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960CPD-8TT-L"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
    ]


class WS_C2960CX_8PC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960CX-8PC-L"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=[Speed.gigabit])]


class WS_C2960CX_8TC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960CX-8TC-L"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=[Speed.gigabit])]


class WS_C2960C_12PC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960C-12PC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960C_8PC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960C-8PC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960C_8TC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960C-8TC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960C_8TC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C2960C-8TC-S"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960G_24TC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960G-24TC-L"]
    ports: list[PortGroup] = [PortGroup(count=26, speeds=[Speed.gigabit])]


class WS_C2960S_24PS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960S-24PS-L"]
    ports: list[PortGroup] = [PortGroup(count=28, speeds=[Speed.gigabit])]


class WS_C2960S_24TS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960S-24TS-L"]
    ports: list[PortGroup] = [PortGroup(count=28, speeds=[Speed.gigabit])]


class WS_C2960S_48FPS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960S-48FPS-L"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C2960S_48LPS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960S-48LPS-L"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C2960S_48TS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960S-48TS-L"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C2960X_24PD_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-24PD-L"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
    ]


class WS_C2960X_24PS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-24PS-L"]
    ports: list[PortGroup] = [PortGroup(count=28, speeds=[Speed.gigabit])]


class WS_C2960X_24TS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-24TS-L"]
    ports: list[PortGroup] = [PortGroup(count=28, speeds=[Speed.gigabit])]


class WS_C2960X_48FPD_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-48FPD-L"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
    ]


class WS_C2960X_48FPS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-48FPS-L"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C2960X_48LPS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-48LPS-L"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C2960X_48TS_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-48TS-L"]
    ports: list[PortGroup] = [PortGroup(count=52, speeds=[Speed.gigabit])]


class WS_C2960X_48TS_LL(CiscoIOSDevice):
    models: list[str] = ["WS-C2960X-48TS-LL"]
    ports: list[PortGroup] = [PortGroup(count=50, speeds=[Speed.gigabit])]


class WS_C2960_24PC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-24PC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_24TC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960+24TC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_24TC_L_2(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-24TC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_24TC_S(CiscoIOSDevice):
    models: list[str] = ["WS-C2960+24TC-S"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_24TC_S_2(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-24TC-S"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_24TT_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-24TT-L"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_48PST_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960+48PST-L"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.fast_ethernet]),
        PortGroup(count=4, speeds=[Speed.gigabit]),
    ]


class WS_C2960_48TC_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-48TC-L"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_48TT_L(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-48TT-L"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class WS_C2960_48TT_S(CiscoIOSDevice):
    models: list[str] = ["WS-C2960-48TT-S"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]
