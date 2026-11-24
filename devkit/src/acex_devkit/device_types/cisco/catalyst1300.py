"""Catalyst 1300 hardware model declarations.

The Catalyst 1300 runs Cisco Business firmware, not IOS or IOS-XE. Port counts, uplink types and which models have PoE
come from the Catalyst 1300 Series data sheet, not from an observed device. Stacking is not modelled, and neither is
the PoE budget.
"""

from acex_devkit.device_types.cisco.base import CiscoBusinessDevice
from acex_devkit.models.device_type import PortGroup, PortMedia, Speed


class C1300_8P_E_2G(CiscoBusinessDevice):
    models: list[str] = ["C1300-8P-E-2G"]
    ports: list[PortGroup] = [
        PortGroup(count=8, speeds=[Speed.gigabit], media=PortMedia.rj45),
        PortGroup(count=2, speeds=[Speed.gigabit], media=PortMedia.sfp),
    ]
    notes: str | None = (
        "The two uplinks are combo ports: each is a copper port and an SFP slot, of which one is active at a time. "
        "Takes an external power supply."
    )


class C1300_24P_4X(CiscoBusinessDevice):
    models: list[str] = ["C1300-24P-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit], media=PortMedia.rj45),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], media=PortMedia.sfp_plus),
    ]


class C1300_48P_4X(CiscoBusinessDevice):
    models: list[str] = ["C1300-48P-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit], media=PortMedia.rj45),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], media=PortMedia.sfp_plus),
    ]


class C1300_48P_4G(CiscoBusinessDevice):
    models: list[str] = ["C1300-48P-4G"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit], media=PortMedia.rj45),
        PortGroup(count=4, speeds=[Speed.gigabit], media=PortMedia.sfp),
    ]


class C1300_48T_4G(CiscoBusinessDevice):
    models: list[str] = ["C1300-48T-4G"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit], media=PortMedia.rj45),
        PortGroup(count=4, speeds=[Speed.gigabit], media=PortMedia.sfp),
    ]
