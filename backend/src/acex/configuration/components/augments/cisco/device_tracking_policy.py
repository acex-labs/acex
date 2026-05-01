"""
Cisco IOS / IOS-XE device-tracking policy attachment.

Attaches a globally-defined device-tracking policy by name to an interface
or interface template. Renders to `device-tracking attach-policy <name>`.

The policy itself (`device-tracking policy IPDT_POLICY { ... }`) is currently
defined out-of-band on the device; this augment only models the attachment.
"""
from typing import Literal

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.interfaces import (
    FrontpanelPort,
    InterfaceTemplate,
    LagInterface,
    Loopback,
    ManagementPort,
    Subinterface,
    Svi,
)
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoDeviceTrackingPolicyAttributes(AugmentAttributes):
    "Attaches a named Cisco device-tracking policy to an interface or interface template."
    type: Literal["cisco.device_tracking_policy"] = "cisco.device_tracking_policy"
    policy_name: AttributeValue[str]


class CiscoDeviceTrackingPolicy(Augment):
    type = "cisco.device_tracking_policy"
    model_cls = CiscoDeviceTrackingPolicyAttributes
    valid_targets = (
        InterfaceTemplate,
        FrontpanelPort,
        LagInterface,
        Loopback,
        ManagementPort,
        Subinterface,
        Svi,
    )
    default_vendor = "cisco"
