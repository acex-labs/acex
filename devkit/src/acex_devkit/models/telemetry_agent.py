from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.capability import TelemetryCapability


class InfluxDBVersion(StrEnum):
    v1 = "v1"
    v2 = "v2"
    v3 = "v3"


class SnmpVersion(StrEnum):
    v2c = "2c"
    v3 = "3"
    both = "both"


class SnmpSecLevel(StrEnum):
    no_auth_no_priv = "noAuthNoPriv"
    auth_no_priv = "authNoPriv"
    auth_priv = "authPriv"


class OutputDestinationBase(BaseModel):
    influxdb_version: InfluxDBVersion = InfluxDBVersion.v2
    url: str = "http://localhost:8086"
    token: str | None = None
    organization: str | None = None
    bucket: str | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


class OutputDestinationCreate(OutputDestinationBase):
    pass


class OutputDestinationUpdate(BaseModel):
    influxdb_version: InfluxDBVersion | None = None
    url: str | None = None
    token: str | None = None
    organization: str | None = None
    bucket: str | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


class OutputDestinationResponse(PersistedResponse, OutputDestinationBase):
    pass


class TelemetryAgentMatchRuleBase(BaseModel):
    region: str | None = None
    site: str | None = None
    vendor: str | None = None
    os: str | None = None
    status: str | None = None
    role: str | None = None


class TelemetryAgentMatchRuleResponse(PersistedResponse, TelemetryAgentMatchRuleBase):
    pass


class TelemetryAgentMatchRuleCreate(TelemetryAgentMatchRuleBase):
    pass


class TelemetryAgentBase(BaseModel):
    name: str
    description: str | None = None
    snmp_version: SnmpVersion = SnmpVersion.v2c
    snmp_trap_port: int = 162
    syslog_port: int = 514
    snmpv3_sec_level: SnmpSecLevel | None = None
    # Inline security name — only used with noAuthNoPriv (no credential needed).
    # With authNoPriv/authPriv the username comes from the mapped credential.
    snmpv3_sec_name: str | None = None
    # References to Credentials holding trap receiver secrets.
    # snmpv2c_credential_id → credential of type "snmp_community" (field: community)
    # snmpv3_credential_id → credential of type "snmpv3" (fields: username/auth_*/priv_*)
    snmpv2c_credential_id: int | None = None
    snmpv3_credential_id: int | None = None


class TelemetryAgentCreate(TelemetryAgentBase):
    capabilities: list[TelemetryCapability] = []


class TelemetryAgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    capabilities: list[TelemetryCapability] | None = None
    snmp_version: SnmpVersion | None = None
    snmp_trap_port: int | None = None
    syslog_port: int | None = None
    snmpv3_sec_level: SnmpSecLevel | None = None
    snmpv3_sec_name: str | None = None
    snmpv2c_credential_id: int | None = None
    snmpv3_credential_id: int | None = None


class TelemetryAgentAck(BaseModel):
    config_revision: int


class TelemetryAgentResponse(PersistedResponse, TelemetryAgentBase):
    config_revision: int = 0
    last_config_poll: str | None = None
    acked_revision: int = 0
    acked_at: str | None = None
    capabilities: list[TelemetryCapability] = []
    nodes: list[int] = []
    rules: list[TelemetryAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []
    outputs: list[OutputDestinationResponse] = []


__all__ = [
    "InfluxDBVersion",
    "OutputDestinationBase",
    "OutputDestinationCreate",
    "OutputDestinationResponse",
    "OutputDestinationUpdate",
    "SnmpSecLevel",
    "SnmpVersion",
    "TelemetryAgentAck",
    "TelemetryAgentBase",
    "TelemetryAgentCreate",
    "TelemetryAgentMatchRuleBase",
    "TelemetryAgentMatchRuleCreate",
    "TelemetryAgentMatchRuleResponse",
    "TelemetryAgentResponse",
    "TelemetryAgentUpdate",
]
