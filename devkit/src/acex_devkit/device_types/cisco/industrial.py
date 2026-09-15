"""Industrial Ethernet hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice
from acex_devkit.models.device_type import PortGroup, Speed


class IE_2000_4TS_L(CiscoIOSDevice):
    models: list[str] = ["IE-2000-4TS-L"]
    ports: list[PortGroup] = [
        PortGroup(count=4, speeds=[Speed.fast_ethernet]),
        PortGroup(count=2, speeds=[Speed.gigabit]),
    ]


class IE_4010_4S24P(CiscoIOSDevice):
    models: list[str] = ["IE-4010-4S24P"]
    ports: list[PortGroup] = [PortGroup(count=28, speeds=[Speed.gigabit])]
