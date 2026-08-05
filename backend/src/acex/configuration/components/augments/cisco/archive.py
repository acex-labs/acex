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

from typing import Literal

from acex.configuration.components.augments.base import Augment
from acex.configuration.components.system.logging import FileLogging
from acex_devkit.models import AttributeValue
from acex_devkit.models.composed_configuration import AugmentAttributes


class CiscoArchiveAttributes(AugmentAttributes):
    """
    archive commands
    """

    type: Literal["cisco.archive"] = "cisco.archive"
    enabled: AttributeValue[bool] | None = None
    log_config: AttributeValue[bool] | None = None  # config  Logging changes to the running configuration
    path: AttributeValue[str] | None = None  # ex: "flash:" # filename is not enough in "FileLogging" model
    write_memory: AttributeValue[bool] | None = None  # Enable automatic backup generation during write memory
    time_period: AttributeValue[int] | None = None  # Period in minutes to automatically archive the running-config
    maximum: AttributeValue[int] | None = None  # max backup copies, handled in "FileLogging" model, see "rotate"
    rollback_filter: AttributeValue[bool] | None = None  # Rollback filter adaptive learning for rollback
    rollback_retry: AttributeValue[int] | None = None  # Rollback retry timeout in seconds


class CiscoArchive(Augment):
    """
    archive commands
    """

    type = "cisco.archive"
    model_cls = CiscoArchiveAttributes
    valid_targets = (FileLogging,)
    default_vendor = "cisco"
