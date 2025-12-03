from pydantic import BaseModel
from acex.models.attribute_value import AttributeValue
from enum import Enum
from typing import Optional, Dict


class LoggingServerBase(BaseModel): ...
    #name: str = None


class LoggingSeverity(str, Enum): 
    EMERGENCY = "EMERGENCY"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFORMATIONAL = "INFORMATIONAL"
    DEBUG = "DEBUG"


class LoggingConfig(BaseModel):
    rate_limit: Optional[AttributeValue[int]] = None
    severity: Optional[AttributeValue[LoggingSeverity]] = None

class LoggingConsole(BaseModel):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True

class RemoteServer(BaseModel):
    name: str = None
    host: str = None
    port: Optional[AttributeValue][int] = 514
    transfer: Optional[AttributeValue][str] = 'udp'
    source_address: Optional[AttributeValue][str] = None

class VtyLines(BaseModel):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True

class GlobalConfig(BaseModel):
    name: str = None
    buffer_size: int = 4096

class FileConfig(BaseModel):
    name: str = None # object name
    filename: str = None # name of the file
    rotate: int = None # How many versions to keep
    max_size: int = None # Think Ciscos "logging buffered"
    facility: LoggingSeverity # Level for logs


class LoggingEvent(BaseModel):
    enabled: bool
    severity: LoggingSeverity


class LoggingEvents(BaseModel):
    events: Optional[Dict[str, LoggingEvent]] = {}