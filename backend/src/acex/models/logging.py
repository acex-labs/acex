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

class LoggingFacility(str, Enum):
    # Some are specific for Juniper devices and are taken directly from their documentation.
    KERN = "KERN"
    USER = "USER"
    DAEMON = "DAEMON"
    AUTHORIZATION = "AUTHORIZATION"
    FTP = "FTP"
    NTP = "NTP"
    DFC = "DFC"
    EXTERNAL = "EXTERNAL"
    FIREWALL = "FIREWALL"
    PFE = "PFE"
    CONFLICTLOG = "CONFLICTLOG"
    CHANGELOG = "CHANGELOG"
    INTERACTIVE_COMMANDS = "INTERACTIVE_COMMANDS"

class Reference(BaseModel): ...

class LoggingConfig(BaseModel):
    rate_limit: Optional[AttributeValue[int]] = None
    severity: Optional[AttributeValue[LoggingSeverity]] = None
    buffer_size: Optional[AttributeValue[int]] = 4096

class Console(BaseModel):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True

class RemoteServer(BaseModel):
    name: str = None
    host: str = None
    port: Optional[int] = 514
    transfer: Optional[str] = 'udp'
    source_address: Optional[AttributeValue[str]] = None # Can be an IP address or an interface reference

class VtyLine(BaseModel):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True
    transport_input: Optional[str] = 'ssh' # default is SSH. Mostly used by Cisco.

class FileLogging(BaseModel):
    name: str = None # object name
    filename: str = None # name of the file
    rotate: Optional[int] = None # How many versions to keep. Juniper specific. 
    max_size: Optional[int] = None # Max size in bytes. Used both for Cisco and Juniper. 
    min_size: Optional[int] = None # Min size in bytes. Only used for Cisco.
    facility: LoggingFacility # Type of log
    severity: LoggingSeverity # Severity level

class LoggingEvent(BaseModel):
    enabled: bool
    severity: LoggingSeverity


class LoggingEvents(BaseModel):
    events: Optional[Dict[str, LoggingEvent]] = {}