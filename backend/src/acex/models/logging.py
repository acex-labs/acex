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

class Reference(BaseModel): ...

class LoggingConfig(BaseModel):
    rate_limit: Optional[AttributeValue[int]] = None
    severity: Optional[AttributeValue[LoggingSeverity]] = None
    buffer_size: Optional[AttributeValue[int]] = 4096

class LoggingConsole(BaseModel):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True

class RemoteServer(BaseModel):
    name: str = None
    host: str = None
    port: Optional[int] = 514
    transfer: Optional[str] = 'udp'
    source_interface: Optional[str] = None
    
    # We will not use interface reference here for now as source_interface can be both an IP address or an interface.
    #source_address: Optional[str] = None
    # Could be "vlan2, mgmt0" etc.
    #source_interface: Optional[Reference] = None
    # Source address as an option too?
    #source_address: Optional[str] = None

class VtyLines(BaseModel):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True
    transport_input: Optional[str] = 'ssh'

#class GlobalConfig(BaseModel):
#    name: str = None
#    buffer_size: int = 4096

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