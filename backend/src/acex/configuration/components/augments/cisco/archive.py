"""
Cisco archive commands

Archive configuration commands:
  log           Logging commands
  maximum       maximum number of backup copies # Handled in "FileLogging" model, see "rotate
  path          path for backups 
  rollback      Rollback parameters
    filter      Rollback filter adaptive learning for rollback
    retry       Rollback retry timeout
  time-period   Period of time in minutes to automatically archive the running-config
  write-memory  Enable automatic backup generation during write memory
  
Ex:
archive
 log config
  logging enable
 path flash:
 write-memory
"""
from typing import Literal, Optional

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.logging import FileLogging
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes
    
class CiscoArchiveAttributes(AugmentAttributes):
    """
    archive commands
    """
    type: Literal["cisco.archive"] = "cisco.archive"
    enabled: Optional[AttributeValue[bool]] = None
    log_config: Optional[AttributeValue[bool]] = None # config  Logging changes to the running configuration
    path: Optional[AttributeValue[str]] = None # ex: "flash:" # filename is not enough in "FileLogging" model
    write_memory: Optional[AttributeValue[bool]] = None # Enable automatic backup generation during write memory
    time_period: Optional[AttributeValue[int]] = None # Period of time in minutes to automatically archive the running-config
    maximum: Optional[AttributeValue[int]] = None # maximum number of backup copies, handled in "FileLogging" model, see "rotate"
    rollback_filter: Optional[AttributeValue[bool]] = None # Rollback filter adaptive learning for rollback
    rollback_retry: Optional[AttributeValue[int]] = None # Rollback retry timeout in seconds

class CiscoArchive(Augment):
    """
    archive commands
    """
    type = "cisco.archive"
    model_cls = CiscoArchiveAttributes
    valid_targets = (FileLogging, )
    default_vendor = "cisco"