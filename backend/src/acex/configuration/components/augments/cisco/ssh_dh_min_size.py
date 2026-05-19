"""
Cisco SSH Diffie-Hellman minimum key size.

Renders to ``ip ssh dh min size <bits>``.
"""
from typing import Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.ssh import SshServer
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoSshDhMinSizeAttributes(AugmentAttributes):
    "Minimum Diffie-Hellman key size negotiated by the SSH server."
    type: Literal["cisco_dh_min_size"] = "cisco_dh_min_size"
    dh_min_size: Optional[AttributeValue[int]] = None


class CiscoSshDhMinSize(Augment):
    type = "cisco_dh_min_size"
    model_cls = CiscoSshDhMinSizeAttributes
    valid_targets = (SshServer, )
    default_vendor = "cisco"
