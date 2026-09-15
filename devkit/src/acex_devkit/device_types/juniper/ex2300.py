"""Juniper EX2300 hardware model declarations.

Access-layer fixed-configuration switches. Uplinks are built in on pic 1.
"""

from acex_devkit.device_types.juniper.base import JuniperEXDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed

GE = [Speed.gigabit]
MGIG = [Speed.gigabit, Speed.two_and_half_gigabit]
UPLINK_4X10G = PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1, media=PortMedia.sfp_plus)


class EX2300_24T(JuniperEXDevice):
    models: list[str] = ["EX2300-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G]


class EX2300_48T(JuniperEXDevice):
    models: list[str] = ["EX2300-48T"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G]


class EX2300_24P(JuniperEXDevice):
    models: list[str] = ["EX2300-24P"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G]
    notes: str | None = "PoE+ variant of EX2300-24T; port layout identical."


class EX2300_48P(JuniperEXDevice):
    models: list[str] = ["EX2300-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G]
    notes: str | None = "PoE+ variant of EX2300-48T; port layout identical."


class EX2300_24MP(JuniperEXDevice):
    models: list[str] = ["EX2300-24MP"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=MGIG, media=PortMedia.rj45), UPLINK_4X10G]


class EX2300_48MP(JuniperEXDevice):
    models: list[str] = ["EX2300-48MP"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=MGIG, media=PortMedia.rj45), UPLINK_4X10G]


class EX2300_C_12T(JuniperEXDevice):
    models: list[str] = ["EX2300-C-12T"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=2, speeds=GE, module_index=1, media=PortMedia.sfp),
    ]
    notes: str | None = "Compact fanless; 2 x 1G SFP uplinks rather than the 4 x 10G of the rack models."


class EX2300_C_12P(JuniperEXDevice):
    models: list[str] = ["EX2300-C-12P"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=GE, media=PortMedia.rj45),
        PortGroup(count=2, speeds=GE, module_index=1, media=PortMedia.sfp),
    ]
    notes: str | None = "PoE+ variant of EX2300-C-12T; port layout identical."
