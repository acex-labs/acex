"""
Cisco VTPv3 primary-server marker.

Marks the device as primary server in a Cisco VTPv3 domain. Cisco-only
concept (VTP itself is Cisco-proprietary, and the primary-server role
exists only in v3). Renders to::

    vtp primary server
"""
from typing import Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.vtp import Vtp
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoVtpPrimaryServerAttributes(AugmentAttributes):
    "Marks this VTP node as primary server (Cisco VTPv3 proprietary)."
    type: Literal["cisco.vtp_primary_server"] = "cisco.vtp_primary_server"
    enabled: Optional[AttributeValue[bool]] = None


class CiscoVtpPrimaryServer(Augment):
    type = "cisco.vtp_primary_server"
    model_cls = CiscoVtpPrimaryServerAttributes
    valid_targets = (Vtp,)
    default_vendor = "cisco"
