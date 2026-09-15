"""Generic and virtual hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice, CiscoIOSXEDevice
from acex_devkit.models.device_type import PortGroup, Speed


class Cisco(CiscoIOSDevice):
    models: list[str] = ["Cisco"]
    notes: str | None = "Generic vendor string; no deterministic physical interface layout."


class c9kv_uadp_8p(CiscoIOSXEDevice):
    models: list[str] = ["c9kv-uadp-8p"]
    ports: list[PortGroup] = [
        PortGroup(count=24, speeds=[Speed.gigabit]),
        PortGroup(count=4, speeds=[Speed.ten_gigabit]),
    ]
    notes: str | None = (
        "Used in CML. Model is a test model which can contain more, or less, ports. Templates in built "
        "for a general switch."
    )
