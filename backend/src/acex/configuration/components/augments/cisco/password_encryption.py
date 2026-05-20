"""
Service password encryption.
"""
from typing import Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system import SystemConfig
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoServicePasswordEncryptionAttributes(AugmentAttributes):
    "Enables service password encryption."
    type: Literal["cisco_service_password_encryption"] = "cisco_service_password_encryption"
    enabled: Optional[AttributeValue[bool]] = None


class CiscoServicePasswordEncryption(Augment):
    type = "cisco_service_password_encryption"
    model_cls = CiscoServicePasswordEncryptionAttributes
    valid_targets = (SystemConfig, )
    default_vendor = "cisco"
