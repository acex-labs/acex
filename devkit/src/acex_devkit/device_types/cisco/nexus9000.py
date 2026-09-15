"""Nexus 9000 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoNXOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class N9K_C93180YC_FX(CiscoNXOSDevice):
    models: list[str] = ["N9K-C93180YC-FX"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit, Speed.ten_gigabit, Speed.twentyfive_gigabit], module_index=1),
        PortGroup(count=6, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit], module_index=1),
    ]
    stackable: bool = False


class N9K_C93180YC_FX3(CiscoNXOSDevice):
    models: list[str] = ["N9K-C93180YC-FX3"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit, Speed.ten_gigabit, Speed.twentyfive_gigabit], module_index=1),
        PortGroup(count=6, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit], module_index=1),
    ]
    stackable: bool = False


class N9K_C9332C(CiscoNXOSDevice):
    models: list[str] = ["N9K-C9332C"]
    ports: list[PortGroup] = [
        PortGroup(count=32, speeds=[Speed.forty_gigabit, Speed.hundred_gigabit], module_index=1),
    ]
    stackable: bool = False
