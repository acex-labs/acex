from acex.configuration.components.base_component import ConfigComponent
from acex.models.logging_server import (
    RemoteServers,
    ConsoleLines,
    VtyLines,
    GlobalConfig,
    FileConfig
)

class LoggingBase(ConfigComponent): ...

class RemoteLogging(LoggingBase):
    type = 'remote_servers'
    model_cls = RemoteServers

class ConsoleLogging(LoggingBase):
    type = 'console'
    model_cls = ConsoleLines

class VtyLogging(LoggingBase):
    type = 'vty'
    model_cls = VtyLines

class GlobalLogging(LoggingBase):
    type= 'global'
    model_cls = GlobalConfig

class FileLogging(LoggingBase):
    type = 'file'
    model_cls = FileConfig