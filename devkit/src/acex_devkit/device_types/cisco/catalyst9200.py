"""Catalyst 9200 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSXEDevice
from acex_devkit.device_types.cisco.modules import C9200_NM_SLOT
from acex_devkit.models.device_type import ModuleSlot, PortGroup, Speed


class C9200CX_12P_2X2G(CiscoIOSXEDevice):
    models: list[str] = ["C9200CX-12P-2X2G"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=[Speed.gigabit]),
        PortGroup(count=2, speeds=[Speed.ten_gigabit]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class C9200L_24P_4G(CiscoIOSXEDevice):
    models: list[str] = ["C9200L-24P-4G"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.gigabit], module_index=1),
    ]
    notes: str | None = (
        "Base/fixed ports encoded; non-L variants may require selected uplink module if not explicit in SKU."
    )


class C9200L_24P_4X(CiscoIOSXEDevice):
    models: list[str] = ["C9200L-24P-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1),
    ]
    notes: str | None = (
        "Base/fixed ports encoded; non-L variants may require selected uplink module if not explicit in SKU."
    )


class C9200L_48P_4G(CiscoIOSXEDevice):
    models: list[str] = ["C9200L-48P-4G"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.gigabit], module_index=1),
    ]
    notes: str | None = (
        "Base/fixed ports encoded; non-L variants may require selected uplink module if not explicit in SKU."
    )


class C9200L_48P_4X(CiscoIOSXEDevice):
    models: list[str] = ["C9200L-48P-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1),
    ]
    notes: str | None = (
        "Base/fixed ports encoded; non-L variants may require selected uplink module if not explicit in SKU."
    )


class C9200_24PB(CiscoIOSXEDevice):
    models: list[str] = ["C9200-24PB"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9200_NM_SLOT)]
    notes: str | None = (
        "Base/fixed ports encoded; non-L variants may require selected uplink module if not explicit in SKU."
    )


class C9200_48PB(CiscoIOSXEDevice):
    models: list[str] = ["C9200-48PB"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9200_NM_SLOT)]
    notes: str | None = (
        "Base/fixed ports encoded; non-L variants may require selected uplink module if not explicit in SKU."
    )
