"""MikroTik routers: the hEX, RB and CCR series.

Port counts, speeds and cages come from MikroTik's product pages, not from an observed device. The order of the groups
follows the front panel as the page lists it; check it against a device before a driver numbers ports from it.
"""

from acex_devkit.device_types.mikrotik.base import MikroTikDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed

GE = [Speed.gigabit]
TEN_GE = [Speed.ten_gigabit]


class RB750Gr3(MikroTikDevice):
    models: list[str] = ["RB750Gr3", "hEX"]
    ports: list[PortGroup] = [PortGroup(count=5, speeds=GE, media=PortMedia.rj45)]


class RB760iGS(MikroTikDevice):
    models: list[str] = ["RB760iGS", "hEX S"]
    ports: list[PortGroup] = [
        PortGroup(count=5, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=1, speeds=GE, media=PortMedia.sfp),
    ]
    notes: str | None = "The SFP cage takes 1.25 Gbit/s modules."


class RB4011iGSRM(MikroTikDevice):
    models: list[str] = ["RB4011iGS+RM"]
    ports: list[PortGroup] = [
        PortGroup(count=10, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=1, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]


class RB5009UGSIN(MikroTikDevice):
    models: list[str] = ["RB5009UG+S+IN"]
    ports: list[PortGroup] = [
        PortGroup(count=1, speeds=[Speed.two_and_half_gigabit], media=PortMedia.rj45),
        PortGroup(count=7, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=1, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]
    notes: str | None = "One 2.5 Gbit/s port and seven gigabit ports, all RJ-45, and one 10G SFP+ cage."


class CCR2004_16G_2S(MikroTikDevice):
    models: list[str] = ["CCR2004-16G-2S+"]
    ports: list[PortGroup] = [
        PortGroup(count=16, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=2, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]
