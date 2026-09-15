"""ISR / Catalyst 8000 routers hardware model declarations.

A device declares the model strings it reports and its front-panel port runs.
Interface naming is the driver's concern, not this file's.
"""

from acex_devkit.device_types.cisco.base import CiscoIOSDevice, CiscoIOSXEDevice
from acex_devkit.models.device_type import PortGroup, Speed


class C1841(CiscoIOSDevice):
    models: list[str] = ["1841"]
    ports: list[PortGroup] = [PortGroup(count=2, speeds=[Speed.gigabit])]
    stackable: bool = False


class C8200_1N_4T(CiscoIOSXEDevice):
    models: list[str] = ["C8200-1N-4T"]
    ports: list[PortGroup] = [PortGroup(count=4, speeds=[Speed.gigabit])]
    stackable: bool = False


class CISCO1941_K9(CiscoIOSDevice):
    models: list[str] = ["CISCO1941/K9"]
    ports: list[PortGroup] = [PortGroup(count=2, speeds=[Speed.gigabit])]
    stackable: bool = False
