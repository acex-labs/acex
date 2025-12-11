from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.models.composed_configuration import ReferenceTo
from acex.models.logging import (
    LoggingConfig as LoggingConfigAttributes,
    Console as ConsoleAttributes,
    RemoteServer as RemoteServerAttributes,
    LoggingEvent as LoggingEventAttributes,
    VtyLine as VtyLineAttributes,
    FileLogging as FileLoggingAttributes
)


class LoggingConfig(ConfigComponent):
    type= 'logging_config'
    model_cls = LoggingConfigAttributes

class Console(ConfigComponent):
    type = 'console'
    model_cls = ConsoleAttributes

class VtyLine(ConfigComponent):
    type = 'vty_line'
    model_cls = VtyLineAttributes

class RemoteServer(ConfigComponent):
    type = 'remote_server'
    model_cls = RemoteServerAttributes

class LoggingEvent(ConfigComponent):
    type = 'logging_event'
    model_cls = LoggingEventAttributes

class FileLogging(ConfigComponent):
    type = 'file_logging'
    #model_cls = FileConfigAttributes
    model_cls = FileLoggingAttributes