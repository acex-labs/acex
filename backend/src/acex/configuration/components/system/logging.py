from acex.configuration.components.base_component import ConfigComponent
from acex.models.logging import (
    LoggingConfig,
    LoggingConsole,
    RemoteServer,
    LoggingEvent,
    VtyLines,
    FileConfig,
    GlobalConfig
)


class LoggingConfig(ConfigComponent):
    type= 'logging_config'
    model_cls = LoggingConfig

class GlobalConfig(ConfigComponent):
    type= 'logging_config'
    model_cls = GlobalConfig

class LoggingConsole(ConfigComponent):
    type = 'console'
    model_cls = LoggingConsole

class VtyLines(ConfigComponent):
    type = 'vty_lines'
    model_cls = VtyLines

class LoggingServer(ConfigComponent):
    type = 'logging_server'
    model_cls = RemoteServer

class LoggingEvent(ConfigComponent):
    type = 'logging_event'
    model_cls = LoggingEvent

class FileConfig(ConfigComponent):
    type = 'file_config'
    model_cls = FileConfig