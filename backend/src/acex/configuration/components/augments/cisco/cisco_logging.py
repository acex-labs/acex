"""
Cisco logging commands

no logging console
logging trap notifications
ip ssh logging events
"""
from typing import Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.ssh import SshServer
from acex.configuration.components.system.logging import Console, LoggingConfig
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes
from acex_devkit.models.logging import LoggingSeverity

class CiscoLoggingTrapAttributes(AugmentAttributes):
    """
    logging trap notifications
    """
    type: Literal["cisco.trap_logging"] = "cisco.logging"
    severity: Optional[AttributeValue[LoggingSeverity]] = None # Ex. INFORMATIONAL

class CiscoLoggingTrap(Augment):
    """
    logging trap notifications
    """
    type = "cisco.trap_logging"
    model_cls = CiscoLoggingTrapAttributes
    valid_targets = (LoggingConfig, )
    default_vendor = "cisco"
    
class CiscoLoggingConsoleAttributes(AugmentAttributes):
    """"
    no logging console
    """
    type: Literal["cisco.console_logging"] = "cisco.console_logging"
    enabled: Optional[AttributeValue[bool]] = None

class CiscoLoggingConsole(Augment):
    type = "cisco.console_logging"
    model_cls = CiscoLoggingConsoleAttributes
    valid_targets = (LoggingConfig, )
    default_vendor = "cisco"
    
class CiscoLoggingSshAttributes(AugmentAttributes):
    """
    ip ssh logging events
    """
    type: Literal["cisco.ssh_logging"] = "cisco.ssh_logging"
    enabled: Optional[AttributeValue[bool]] = None

class CiscoLoggingSsh(Augment):
    """
    ip ssh logging events
    """
    type = "cisco.ssh_logging"
    model_cls = CiscoLoggingSshAttributes
    valid_targets = (LoggingConfig, )
    default_vendor = "cisco"