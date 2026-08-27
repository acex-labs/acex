from acex_devkit.models.capability import TelemetryCapability
from acex_devkit.models.telemetry_agent import (
    InfluxDBVersion,
    SnmpSecLevel,
    SnmpVersion,
)
from acex_devkit.models.telemetry_agent import (
    TelemetryAgentBase as _TelemetryAgentSchema,
)
from acex_devkit.models.telemetry_agent import (
    TelemetryAgentMatchRuleBase as _TelemetryAgentMatchRuleSchema,
)
from sqlmodel import Field, SQLModel


class TelemetryAgent(_TelemetryAgentSchema, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    config_revision: int = Field(default=0)
    last_config_poll: str | None = None
    acked_revision: int = Field(default=0)
    acked_at: str | None = None
    snmpv2c_credential_id: int | None = Field(default=None, foreign_key="credential.id")
    snmpv3_credential_id: int | None = Field(default=None, foreign_key="credential.id")


class TelemetryAgentNodeLink(SQLModel, table=True):
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id", primary_key=True)
    node_id: int = Field(foreign_key="node.id", primary_key=True)


class TelemetryAgentCapabilityLink(SQLModel, table=True):
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id", primary_key=True)
    capability: TelemetryCapability = Field(primary_key=True)


class TelemetryAgentMatchRule(_TelemetryAgentMatchRuleSchema, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    telemetry_agent_id: int = Field(foreign_key="telemetryagent.id")


__all__ = [
    "InfluxDBVersion",
    "SnmpSecLevel",
    "SnmpVersion",
    "TelemetryAgent",
    "TelemetryAgentCapabilityLink",
    "TelemetryAgentMatchRule",
    "TelemetryAgentNodeLink",
]
