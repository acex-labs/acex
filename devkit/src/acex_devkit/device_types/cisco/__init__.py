"""Cisco hardware declarations.

Importing this package registers every Cisco device and port module.
One module per hardware family; add a new family by adding a file here.
"""

from acex_devkit.device_types.cisco import (  # noqa: F401  (registers devices)
    catalyst2950,
    catalyst2960,
    catalyst3500,
    catalyst3560,
    catalyst3650,
    catalyst3750,
    catalyst3850,
    catalyst4500,
    catalyst6500,
    catalyst6800,
    catalyst9200,
    catalyst9300,
    catalyst9400,
    catalyst9500,
    generic,
    industrial,
    modules,  # noqa: F401  (registers modules)
    nexus9000,
    routers,
)
from acex_devkit.device_types.cisco.base import (
    CiscoIOSDevice,
    CiscoIOSXEDevice,
    CiscoNetworkModule,
    CiscoNXOSDevice,
)

__all__ = [
    "CiscoIOSDevice",
    "CiscoIOSXEDevice",
    "CiscoNXOSDevice",
    "CiscoNetworkModule",
]
