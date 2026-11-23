"""MikroTik hardware declarations.

Importing this package registers every MikroTik declaration.
"""

from acex_devkit.device_types.mikrotik import routers, switches  # noqa: F401  (registers devices)
from acex_devkit.device_types.mikrotik.base import MikroTikDevice

__all__ = ["MikroTikDevice"]
