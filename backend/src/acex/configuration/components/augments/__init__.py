"""
Vendor- and OS-specific augments that mount on tree components.

Each vendor has its own subdirectory (e.g. `cisco/`, `juniper/`) so it's
clear at a glance which augments are vendor-locked. Integrators can
import from either the convenience namespace::

    from acex.configuration.components.augments import CiscoDeviceTrackingPolicy

or the explicit per-vendor path::

    from acex.configuration.components.augments.cisco import CiscoDeviceTrackingPolicy
"""
from .base import Augment
from .cisco import (
    CiscoDeviceTrackingPolicy,
    CiscoServicePolicy,
    CiscoVtpPrimaryServer,
)
from .juniper import JuniperSnmpCommunityClients

__all__ = [
    "Augment",
    "CiscoDeviceTrackingPolicy",
    "CiscoServicePolicy",
    "CiscoVtpPrimaryServer",
    "JuniperSnmpCommunityClients",
]
