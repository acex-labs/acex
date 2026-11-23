"""Waystream switches seen on a device or in a report.

The model names come from what a device printed: `show version` on an MS4026-AC running 6.3.0-ED-R, and a report of
`show version` on an MS7048-AC running 7.6.2-GD-R. No port layout is declared, because none of the sources states one;
add the port groups when a datasheet or a device does. Until then a model is selectable and has no ports.
"""

from acex_devkit.device_types.waystream.base import WaystreamDevice

NO_PORTS = "No port layout is declared: it has not been checked against a datasheet or a device."


class MS4026AC(WaystreamDevice):
    models: list[str] = ["MS4026-AC"]
    notes: str | None = NO_PORTS


class MS7048AC(WaystreamDevice):
    models: list[str] = ["MS7048-AC"]
    notes: str | None = NO_PORTS
