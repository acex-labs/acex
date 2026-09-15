"""Juniper EX extension modules.

Port counts and speeds come from Juniper product data, not from an observed
device - verify against the datasheet before relying on a module.
"""

from acex_devkit.device_types.juniper.base import JuniperExtensionModule
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed


class EX4400_EM_4S(JuniperExtensionModule):
    models: list[str] = ["EX4400-EM-4S"]
    ports: list[PortGroup] = [
        PortGroup(count=4, speeds=[Speed.ten_gigabit], media=PortMedia.sfp_plus),
    ]


class EX4400_EM_4Y(JuniperExtensionModule):
    models: list[str] = ["EX4400-EM-4Y"]
    ports: list[PortGroup] = [
        PortGroup(count=4, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit], media=PortMedia.sfp28),
    ]


EX4400_EM_SLOT = ["EX4400-EM-4S", "EX4400-EM-4Y"]
