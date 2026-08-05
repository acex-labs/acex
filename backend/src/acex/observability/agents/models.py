from enum import StrEnum

from acex.observability.capability import TelemetryCapability
from sqlmodel import Field, SQLModel


class TelemetryAgentBase(SQLModel):
    name: str
    description: str | None = None


class TelemetryAgent(TelemetryAgentBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    config_revision: int = Field(default=0)
    last_config_poll: str | None = None
    acked_revision: int = Field(default=0)
    acked_at: str | None = None


class TelemetryAgentNodeLink(SQLModel, table=True):
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id", primary_key=True)
    node_id: int = Field(foreign_key="node.id", primary_key=True)


class TelemetryAgentCapabilityLink(SQLModel, table=True):
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id", primary_key=True)
    capability: TelemetryCapability = Field(primary_key=True)


class TelemetryAgentMatchRuleBase(SQLModel):
    region: str | None = None
    site: str | None = None
    vendor: str | None = None
    os: str | None = None
    status: str | None = None
    role: str | None = None


class TelemetryAgentMatchRule(TelemetryAgentMatchRuleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id")


class TelemetryAgentMatchRuleCreate(TelemetryAgentMatchRuleBase):
    pass


class TelemetryAgentMatchRuleResponse(TelemetryAgentMatchRuleBase):
    id: int


class InfluxDBVersion(StrEnum):
    v1 = "v1"
    v2 = "v2"
    v3 = "v3"


class OutputDestinationBase(SQLModel):
    influxdb_version: InfluxDBVersion = InfluxDBVersion.v2
    url: str = "http://localhost:8086"
    # v2 fields
    token: str | None = None
    organization: str | None = None
    bucket: str | None = None
    # v1 fields
    database: str | None = None
    username: str | None = None
    password: str | None = None


class OutputDestination(OutputDestinationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id")


class OutputDestinationCreate(OutputDestinationBase):
    pass


class OutputDestinationUpdate(SQLModel):
    influxdb_version: InfluxDBVersion | None = None
    url: str | None = None
    token: str | None = None
    organization: str | None = None
    bucket: str | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


class OutputDestinationResponse(OutputDestinationBase):
    id: int


class TelemetryAgentCreate(SQLModel):
    name: str
    description: str | None = None
    capabilities: list[TelemetryCapability] = []


class TelemetryAgentUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    capabilities: list[TelemetryCapability] | None = None


class TelemetryAgentAck(SQLModel):
    config_revision: int


class TelemetryAgentResponse(TelemetryAgentBase):
    id: int
    config_revision: int = 0
    last_config_poll: str | None = None
    acked_revision: int = 0
    acked_at: str | None = None
    capabilities: list[TelemetryCapability] = []
    nodes: list[int] = []
    rules: list[TelemetryAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []
    outputs: list[OutputDestinationResponse] = []
