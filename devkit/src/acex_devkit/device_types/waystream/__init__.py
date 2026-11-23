"""Waystream hardware declarations.

Importing this package registers every Waystream declaration.
"""

from acex_devkit.device_types.waystream import switches  # noqa: F401  (registers devices)
from acex_devkit.device_types.waystream.base import WaystreamDevice

__all__ = ["WaystreamDevice"]
