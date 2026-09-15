"""Catalyst 9300 / 9350 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSXEDevice
from acex_devkit.device_types.cisco.modules import C9300_NM_SLOT, C9300X_NM_SLOT
from acex_devkit.models.device_type import ModuleSlot, PortGroup, Speed


class C9300LM_48U_4Y(CiscoIOSXEDevice):
    models: list[str] = ["C9300LM-48U-4Y"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit], module_index=1),
    ]


class C9300L_24P_4G(CiscoIOSXEDevice):
    models: list[str] = ["C9300L-24P-4G"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.gigabit], module_index=1),
    ]


class C9300L_24P_4X(CiscoIOSXEDevice):
    models: list[str] = ["C9300L-24P-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1),
    ]


class C9300L_24UXG_4X(CiscoIOSXEDevice):
    models: list[str] = ["C9300L-24UXG-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1),
    ]


class C9300L_48P_4X(CiscoIOSXEDevice):
    models: list[str] = ["C9300L-48P-4X"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit], module_index=1),
    ]


class C9300X_12Y(CiscoIOSXEDevice):
    models: list[str] = ["C9300X-12Y"]
    ports: list[PortGroup] = [
        PortGroup(count=12, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit]),
    ]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300X_NM_SLOT)]


class C9300X_24Y(CiscoIOSXEDevice):
    models: list[str] = ["C9300X-24Y"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit]),
    ]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300X_NM_SLOT)]


class C9300X_48HX(CiscoIOSXEDevice):
    models: list[str] = ["C9300X-48HX"]
    ports: list[PortGroup] = [
        PortGroup(count=49, speeds=[Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit, Speed.twentyfive_gigabit]),
    ]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300X_NM_SLOT)]


class C9300_24P(CiscoIOSXEDevice):
    models: list[str] = ["C9300-24P"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300_NM_SLOT)]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class C9300_24T(CiscoIOSXEDevice):
    models: list[str] = ["C9300-24T"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300_NM_SLOT)]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class C9300_24UX(CiscoIOSXEDevice):
    models: list[str] = ["C9300-24UX"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]),
    ]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300_NM_SLOT)]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class C9300_48P(CiscoIOSXEDevice):
    models: list[str] = ["C9300-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300_NM_SLOT)]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class C9300_48U(CiscoIOSXEDevice):
    models: list[str] = ["C9300-48U"]
    ports: list[PortGroup] = [
        PortGroup(count=48, speeds=[Speed.gigabit, Speed.two_and_half_gigabit, Speed.five_gigabit, Speed.ten_gigabit]),
    ]
    slots: list[ModuleSlot] = [ModuleSlot(index=1, accepts=C9300_NM_SLOT)]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class C9350_24P(CiscoIOSXEDevice):
    models: list[str] = ["C9350-24P"]
    ports: list[PortGroup] = [PortGroup(count=24, speeds=[Speed.gigabit])]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class C9350_48P(CiscoIOSXEDevice):
    models: list[str] = ["C9350-48P"]
    ports: list[PortGroup] = [PortGroup(count=48, speeds=[Speed.gigabit])]
    notes: str | None = "Base access ports only; modular uplink module not encoded unless present in SKU."


class c9300_4v(CiscoIOSXEDevice):
    models: list[str] = ["c9300-4v"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit]),
    ]
    notes: str | None = (
        "Used in CML. Model is a test model which can contain more, or less, ports. Templates in built "
        "for a general switch."
    )
