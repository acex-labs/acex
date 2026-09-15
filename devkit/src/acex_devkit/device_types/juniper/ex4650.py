"""Juniper EX4650 hardware model declarations.

Compact 25G/100G switch for aggregation and small spine roles.
"""

from acex_devkit.device_types.juniper.base import JuniperEXDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed


class EX4650_48Y(JuniperEXDevice):
    models: list[str] = ["EX4650-48Y", "EX4650-48Y-8C"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit], media=PortMedia.sfp28),
        PortGroup(count=8, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit], module_index=1, media=PortMedia.qsfp28),
    ]
