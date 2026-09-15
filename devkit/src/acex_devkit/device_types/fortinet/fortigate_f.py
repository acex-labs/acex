"""FortiGate F-series hardware model declarations.

Port counts and media come from Fortinet product data, not from an observed
device. The desktop models (40F-100F) are well established; verify the larger
models against the datasheet before relying on them.
"""

from acex_devkit.device_types.fortinet.base import FortiGateDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed

GE = [Speed.gigabit]
TEN_GE = [Speed.ten_gigabit]
VERIFY = "Port breakdown not verified against the datasheet."


class FG_40F(FortiGateDevice):
    models: list[str] = ["FortiGate-40F", "FG-40F"]
    ports: list[PortGroup] = [PortGroup(count=5, speeds=GE, media=PortMedia.rj45)]
    notes: str | None = "1 x WAN plus 4 x internal, all RJ-45."


class FG_60F(FortiGateDevice):
    models: list[str] = ["FortiGate-60F", "FG-60F"]
    ports: list[PortGroup] = [PortGroup(count=10, speeds=GE, media=PortMedia.rj45)]
    notes: str | None = "2 x WAN, 1 x DMZ and 7 x internal switch ports, all RJ-45."


class FG_80F(FortiGateDevice):
    models: list[str] = ["FortiGate-80F", "FG-80F"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=2, speeds=GE, media=PortMedia.sfp),
    ]


class FG_100F(FortiGateDevice):
    models: list[str] = ["FortiGate-100F", "FG-100F"]
    ports: list[PortGroup] = [
        PortGroup(count=16, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=4, speeds=GE, media=PortMedia.sfp),
        PortGroup(count=2, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]


class FG_200F(FortiGateDevice):
    models: list[str] = ["FortiGate-200F", "FG-200F"]
    ports: list[PortGroup] = [
        PortGroup(count=18, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=8, speeds=GE, media=PortMedia.sfp),
        PortGroup(count=4, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]
    notes: str | None = VERIFY


class FG_400F(FortiGateDevice):
    models: list[str] = ["FortiGate-400F", "FG-400F"]
    ports: list[PortGroup] = [
        PortGroup(count=16, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=8, speeds=GE, media=PortMedia.sfp),
        PortGroup(count=4, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]
    notes: str | None = VERIFY


class FG_600F(FortiGateDevice):
    models: list[str] = ["FortiGate-600F", "FG-600F"]
    ports: list[PortGroup] = [
        PortGroup(count=16, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=8, speeds=GE, media=PortMedia.sfp),
        PortGroup(count=8, speeds=TEN_GE, media=PortMedia.sfp_plus),
    ]
    notes: str | None = VERIFY
