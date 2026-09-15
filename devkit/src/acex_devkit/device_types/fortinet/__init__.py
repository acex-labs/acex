"""Fortinet hardware declarations.

Importing this package registers every FortiGate declaration.
"""

from acex_devkit.device_types.fortinet import fortigate_f  # noqa: F401  (registers devices)
from acex_devkit.device_types.fortinet.base import FortiGateDevice

__all__ = ["FortiGateDevice"]
