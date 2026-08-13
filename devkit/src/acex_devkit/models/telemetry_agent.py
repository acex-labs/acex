from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.capability import TelemetryCapability


class InfluxDBVersion(StrEnum):
    v1 = "v1"
    v2 = "v2"
    v3 = "v3"


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


class TelemetryAgentCreate(TelemetryAgentBase):
    capabilities: list[TelemetryCapability] = []


class TelemetryAgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    capabilities: list[TelemetryCapability] | None = None


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
