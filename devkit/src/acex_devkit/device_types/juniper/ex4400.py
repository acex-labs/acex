"""Juniper EX4400 hardware model declarations.

Access ports sit on pic 0, the rear extension module on pic 1. The two rear
100G QSFP28 ports are Virtual Chassis ports by default and are declared on
pic 2; converting them to network ports is a configuration choice.
"""

from acex_devkit.device_types.juniper.base import JuniperEXDevice
from acex_devkit.device_types.juniper.modules import EX4400_EM_SLOT
from acex_devkit.models.device_type import ModuleSlot, PortGroup, PortMedia, Speed

GE = [Speed.gigabit]
MGIG = [Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]
VCP_2X100G = PortGroup(count=2, speeds=[Speed.hundred_gigabit], module_index=2, media=PortMedia.qsfp28)
EM_SLOT = [ModuleSlot(index=1, accepts=EX4400_EM_SLOT)]


class EX4400_24T(JuniperEXDevice):
    models: list[str] = ["EX4400-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT


class EX4400_48T(JuniperEXDevice):
    models: list[str] = ["EX4400-48T"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT


class EX4400_24P(JuniperEXDevice):
    models: list[str] = ["EX4400-24P"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=GE, media=PortMedia.rj45), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT
    notes: str | None = "PoE++ variant of EX4400-24T; port layout identical."


class EX4400_48P(JuniperEXDevice):
    models: list[str] = ["EX4400-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.rj45), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT
    notes: str | None = "PoE++ variant of EX4400-48T; port layout identical."


class EX4400_24MP(JuniperEXDevice):
    models: list[str] = ["EX4400-24MP"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=MGIG, media=PortMedia.rj45), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT


class EX4400_48MP(JuniperEXDevice):
    models: list[str] = ["EX4400-48MP"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=MGIG, media=PortMedia.rj45), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT


class EX4400_24X(JuniperEXDevice):
    models: list[str] = ["EX4400-24X"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit, Speed.ten_gigabit], media=PortMedia.sfp_plus),
        VCP_2X100G,
    ]
    slots: list[ModuleSlot] = EM_SLOT


class EX4400_48F(JuniperEXDevice):
    models: list[str] = ["EX4400-48F"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=GE, media=PortMedia.sfp), VCP_2X100G]
    slots: list[ModuleSlot] = EM_SLOT
