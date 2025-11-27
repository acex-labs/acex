from acex.configuration.components.base_component import ConfigComponent
from acex.models.logging import (
    LoggingConfig,
    LoggingConsole,
    RemoteServer,
    LoggingEvent
)


class LoggingConfig(BaseModel):
    type= 'logging_config'
    model_cls = LoggingConfig


class LoggingConsole(BaseModel):
    type = 'console'
    model_cls = LoggingConsole


class LoggingServer(BaseModel):
    type = 'logging_server'
    model_cls = RemoteServer

class LoggingEvent(BaseModel):
    type = 'logging_event'
    model_cls = LoggingEvents