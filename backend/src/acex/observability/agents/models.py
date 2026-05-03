from typing import Optional
from enum import Enum
from sqlmodel import SQLModel, Field

from acex.observability.capability import TelemetryCapability


class TelemetryAgentBase(SQLModel):
    name: str
    description: Optional[str] = None


class TelemetryAgent(TelemetryAgentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    config_revision: int = Field(default=0)
    last_config_poll: Optional[str] = None


class TelemetryAgentNodeLink(SQLModel, table=True):
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id", primary_key=True)
    node_id: int = Field(foreign_key="node.id", primary_key=True)


class TelemetryAgentCapabilityLink(SQLModel, table=True):
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id", primary_key=True)
    capability: TelemetryCapability = Field(primary_key=True)


class TelemetryAgentMatchRuleBase(SQLModel):
    site: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class TelemetryAgentMatchRule(TelemetryAgentMatchRuleBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id")


class TelemetryAgentMatchRuleCreate(TelemetryAgentMatchRuleBase):
    pass


class TelemetryAgentMatchRuleResponse(TelemetryAgentMatchRuleBase):
    id: int


class InfluxDBVersion(str, Enum):
    v1 = "v1"
    v2 = "v2"
    v3 = "v3"


class OutputDestinationBase(SQLModel):
    influxdb_version: InfluxDBVersion = InfluxDBVersion.v2
    url: str = "http://localhost:8086"
    # v2 fields
    token: Optional[str] = None
    organization: Optional[str] = None
    bucket: Optional[str] = None
    # v1 fields
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class OutputDestination(OutputDestinationBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id")


class OutputDestinationCreate(OutputDestinationBase):
    pass


class OutputDestinationUpdate(SQLModel):
    influxdb_version: Optional[InfluxDBVersion] = None
    url: Optional[str] = None
    token: Optional[str] = None
    organization: Optional[str] = None
    bucket: Optional[str] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class OutputDestinationResponse(OutputDestinationBase):
    id: int


class TelemetryAgentCreate(SQLModel):
    name: str
    description: Optional[str] = None
    capabilities: list[TelemetryCapability] = []


class TelemetryAgentUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: Optional[list[TelemetryCapability]] = None


class TelemetryAgentResponse(TelemetryAgentBase):
    id: int
    config_revision: int = 0
    last_config_poll: Optional[str] = None
    capabilities: list[TelemetryCapability] = []
    nodes: list[int] = []
    rules: list[TelemetryAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []
    outputs: list[OutputDestinationResponse] = []
