"""Actions on IOS and IOS-XE. Each command is a class that builds it and reads its output, so it can be tested
without a device; `CiscoIOSActions` only sends the commands and assembles the results."""

from .facade import CiscoIOSActions

__all__ = ["CiscoIOSActions"]
