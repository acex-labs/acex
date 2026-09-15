"""Juniper EX3400 hardware model declarations.

Fixed uplinks: 4 x 10G SFP+ on pic 1 and 2 x 40G QSFP+ on pic 2.
"""

from acex_devkit.device_types.juniper.base import JuniperEXDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed

GE = [Speed.gigabit]
UPLINK_4X10G = PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1, media=PortMedia.sfp_plus)
UPLINK_2X40G = PortGroup(count=2, speeds=[Speed.forty_gigabit], module_index=2, media=PortMedia.qsfp_plus)


class EX3400_24T(JuniperEXDevice):
    models: list[str] = ["EX3400-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G, UPLINK_2X40G]


class EX3400_48T(JuniperEXDevice):
    models: list[str] = ["EX3400-48T"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G, UPLINK_2X40G]


class EX3400_24P(JuniperEXDevice):
    models: list[str] = ["EX3400-24P"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G, UPLINK_2X40G]
    notes: str | None = "PoE+ variant of EX3400-24T; port layout identical."


class EX3400_48P(JuniperEXDevice):
    models: list[str] = ["EX3400-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G, UPLINK_2X40G]
    notes: str | None = "PoE+ variant of EX3400-48T; port layout identical."
