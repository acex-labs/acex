"""Juniper hardware declarations.

Importing this package registers every Juniper device and extension module.
One module per hardware family; add a new family by adding a file here.
"""

from acex_devkit.device_types.juniper import (  # noqa: F401  (registers devices)
    ex2300,
    ex3400,
    ex4100,
    ex4400,
    ex4650,
    modules,  # noqa: F401  (registers modules)
)
from acex_devkit.device_types.juniper.base import JuniperEXDevice, JuniperExtensionModule

__all__ = ["JuniperEXDevice", "JuniperExtensionModule"]
