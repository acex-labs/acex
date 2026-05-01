"""
Cisco IOS / IOS-XE service-policy attachment.

Attaches an MQC service-policy map by name to an interface or interface
template, in either direction (input/output). Renders to::

    service-policy input <name>
    service-policy output <name>

The policy maps themselves (`policy-map TYPE { class ... }`) are currently
defined out-of-band on the device; this augment only models the
attachment. Either direction can be set independently.
"""
from typing import Literal, Optional

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


class CiscoServicePolicyAttributes(AugmentAttributes):
    "Attaches Cisco MQC service-policy maps (input/output) to an interface or interface template."
    type: Literal["cisco.service_policy"] = "cisco.service_policy"
    input_policy: Optional[AttributeValue[str]] = None
    output_policy: Optional[AttributeValue[str]] = None


class CiscoServicePolicy(Augment):
    type = "cisco.service_policy"
    model_cls = CiscoServicePolicyAttributes
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
