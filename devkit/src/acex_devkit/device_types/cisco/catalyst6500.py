"""Catalyst 6500 hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice


class WS_C6509_E(CiscoIOSDevice):
    models: list[str] = ["WS-C6509-E"]
    notes: str | None = (
        "Modular chassis: interfaces depend on installed supervisor and line cards; chassis alone has no "
        "fixed port map."
    )
