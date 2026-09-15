"""Juniper EX4100 hardware model declarations.

Successor to the EX3400 in the access layer. Uplinks are built in on pic 1;
the F models are fanless with 1G SFP uplinks instead.
"""

from acex_devkit.device_types.juniper.base import JuniperEXDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed

GE = [Speed.gigabit]
MGIG = [Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]
UPLINK_4X25G = PortGroup(
    count=4, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit], module_index=1, media=PortMedia.sfp28
)
UPLINK_4X10G = PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1, media=PortMedia.sfp_plus)
VERIFY = "Uplink speed grade differs across EX4100 sub-models; verify against the datasheet."


class EX4100_24T(JuniperEXDevice):
    models: list[str] = ["EX4100-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X25G]
    notes: str | None = VERIFY


class EX4100_48T(JuniperEXDevice):
    models: list[str] = ["EX4100-48T"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X25G]
    notes: str | None = VERIFY


class EX4100_24P(JuniperEXDevice):
    models: list[str] = ["EX4100-24P"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X25G]
    notes: str | None = VERIFY


class EX4100_48P(JuniperEXDevice):
    models: list[str] = ["EX4100-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X25G]
    notes: str | None = VERIFY


class EX4100_24MP(JuniperEXDevice):
    models: list[str] = ["EX4100-24MP"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=MGIG, media=PortMedia.rj45), UPLINK_4X25G]
    notes: str | None = VERIFY


class EX4100_48MP(JuniperEXDevice):
    models: list[str] = ["EX4100-48MP"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=MGIG, media=PortMedia.rj45), UPLINK_4X25G]
    notes: str | None = VERIFY


class EX4100_F_24T(JuniperEXDevice):
    models: list[str] = ["EX4100-F-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G]
    notes: str | None = "Fanless. " + VERIFY


class EX4100_F_48T(JuniperEXDevice):
    models: list[str] = ["EX4100-F-48T"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), UPLINK_4X10G]
    notes: str | None = "Fanless. " + VERIFY
