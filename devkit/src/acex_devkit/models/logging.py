from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel

from acex_devkit.models.attribute_value import AttributeValue
from acex_devkit.models.augment import Augmentable
from acex_devkit.models.container_entry import ContainerEntry
from acex_devkit.models.reference import Reference


class LoggingServerBase(BaseModel):
    ...
    # name: str = None


class LoggingSeverity(StrEnum):
    EMERGENCY = "EMERGENCY"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFORMATIONAL = "INFORMATIONAL"
    DEBUG = "DEBUG"


class LoggingFacility(StrEnum):
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


class LoggingConfig(Augmentable):
    rate_limit: AttributeValue[int] | None = None
    severity: AttributeValue[LoggingSeverity] | None = None
    buffer_size: AttributeValue[int] | None = None


class Console(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("name",)
    name: AttributeValue[str] | None = None
    line_number: AttributeValue[int] | None = None
    logging_synchronous: AttributeValue[bool] | None = None


class RemoteServer(ContainerEntry, BaseModel):
    identity_fields: ClassVar[tuple[str, ...]] = ("host",)
    name: AttributeValue[str] | None = None
    host: AttributeValue[str] | None = None
    port: AttributeValue[int] | None = None
    transport: AttributeValue[str] | None = None
    source_address: AttributeValue[str] | None = None  # Can be an IP address or an interface reference


class RemoteServers(BaseModel):
    servers: dict[str, RemoteServer] = {}


class VtyLine(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("line_number",)
    name: AttributeValue[str] | None = None
    line_number: AttributeValue[int] | None = None
    logging_synchronous: AttributeValue[bool] | None = None
    transport_input: AttributeValue[str] | None = None  # default is SSH. Mostly used by Cisco.
    ipv4acl: Reference | None = None  # reference to an ACL object. Only used by Cisco.
    ipv6acl: Reference | None = None  # reference to an ACL object. Only used by Cisco.
    acl_direction: AttributeValue[str] | None = None  # direction of ACL, either 'in' or 'out'
    acl_network_instance: AttributeValue[str] | None = None  # network instance where ACL is


class FileLogging(ContainerEntry, Augmentable):
    identity_fields: ClassVar[tuple[str, ...]] = ("filename",)
    name: AttributeValue[str] | None = None  # object name
    filename: AttributeValue[str] | None = None  # name of the file
    rotate: AttributeValue[int] | None = None  # How many versions to keep. Juniper specific.
    max_size: AttributeValue[int] | None = None  # Max size in bytes. Used both for Cisco and Juniper.
    min_size: AttributeValue[int] | None = None  # Min size in bytes. Only used for Cisco.
    facility: AttributeValue[LoggingFacility] | None = None  # Type of log
    severity: AttributeValue[LoggingSeverity] | None = None  # Severity level


class LoggingEvent(BaseModel):
    enabled: AttributeValue[bool] | None = None
    severity: AttributeValue[LoggingSeverity] | None = None


class LoggingEvents(BaseModel):
    events: dict[str, LoggingEvent] | None = None
