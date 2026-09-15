"""Catalyst 4500 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice


class WS_C4503_E(CiscoIOSDevice):
    models: list[str] = ["WS-C4503-E"]
    notes: str | None = (
        "Modular chassis: interfaces depend on installed supervisor and line cards; chassis alone has no "
        "fixed port map."
    )


class WS_C4506(CiscoIOSDevice):
    models: list[str] = ["WS-C4506"]
    notes: str | None = (
        "Modular chassis: interfaces depend on installed supervisor and line cards; chassis alone has no "
        "fixed port map."
    )


class WS_C4507R(CiscoIOSDevice):
    models: list[str] = ["WS-C4507R"]
    notes: str | None = (
        "Modular chassis: interfaces depend on installed supervisor and line cards; chassis alone has no "
        "fixed port map."
    )
