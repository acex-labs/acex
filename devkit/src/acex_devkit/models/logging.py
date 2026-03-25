from pydantic import BaseModel
from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.container_entry import ContainerEntry
from enum import Enum
from typing import ClassVar, Optional, Dict


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
    buffer_size: Optional[AttributeValue[int]] = None

class Console(BaseModel):
    name: Optional[AttributeValue[str]] = None
    line_number: Optional[AttributeValue[int]] = None
    logging_synchronous: Optional[AttributeValue[bool]] = None

class RemoteServer(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("host",)
    name: Optional[AttributeValue[str]] = None
    host: Optional[AttributeValue[str]] = None
    port: Optional[AttributeValue[int]] = None
    transport: Optional[AttributeValue[str]] = None
    source_address: Optional[AttributeValue[str]] = None # Can be an IP address or an interface reference

class RemoteServers(BaseModel):
    servers: Dict[str, RemoteServer] = {}

class VtyLine(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("line_number",)
    name: Optional[AttributeValue[str]] = None
    line_number: Optional[AttributeValue[int]] = None
    logging_synchronous: Optional[AttributeValue[bool]] = None
    transport_input: Optional[AttributeValue[str]] = None # default is SSH. Mostly used by Cisco.

class FileLogging(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("filename",)
    name: Optional[AttributeValue[str]] = None # object name
    filename: Optional[AttributeValue[str]] = None # name of the file
    rotate: Optional[AttributeValue[int]] = None # How many versions to keep. Juniper specific.
    max_size: Optional[AttributeValue[int]] = None # Max size in bytes. Used both for Cisco and Juniper.
    min_size: Optional[AttributeValue[int]] = None # Min size in bytes. Only used for Cisco.
    facility: Optional[AttributeValue[LoggingFacility]] = None # Type of log
    severity: Optional[AttributeValue[LoggingSeverity]] = None # Severity level

class LoggingEvent(BaseModel):
    enabled: Optional[AttributeValue[bool]] = None
    severity: Optional[AttributeValue[LoggingSeverity]] = None


class LoggingEvents(BaseModel):
    events: Optional[Dict[str, LoggingEvent]] = None