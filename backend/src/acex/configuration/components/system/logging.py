from acex.configuration.components.base_component import ConfigComponent
from acex.configuration.components.interfaces import Interface
from acex.models.composed_configuration import ReferenceTo
from acex.models.logging import (
    LoggingConfig as LoggingConfigAttributes,
    LoggingConsole as LoggingConsoleAttributes,
    RemoteServer as RemoteServerAttributes,
    LoggingEvent as LoggingEventAttributes,
    VtyLines as VtyLinesAttributes,
    FileConfig as FileConfigAttributes
)


class LoggingConfig(ConfigComponent):
    type= 'logging_config'
    model_cls = LoggingConfigAttributes

class LoggingConsole(ConfigComponent):
    type = 'console'
    model_cls = LoggingConsoleAttributes

class VtyLines(ConfigComponent):
    type = 'vty_lines'
    model_cls = VtyLinesAttributes

class LoggingServer(ConfigComponent):
    type = 'logging_server'
    model_cls = RemoteServerAttributes

class LoggingEvent(ConfigComponent):
    type = 'logging_event'
    model_cls = LoggingEventAttributes

class FileConfig(ConfigComponent):
    type = 'file_config'
    model_cls = FileConfigAttributes