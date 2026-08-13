from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class ManifestTarget(BaseModel):
    node_id: int
    hostname: str | None = None
    target_ip: str | None = None
    connection_type: str | None = None
    ned_id: str | None = None
    vendor: str | None = None
    os: str | None = None
    credentials: dict[str, int] = {}


class CollectionAgentManifest(BaseModel):
    agent_id: int
    name: str
    config_revision: int = 0
    interval_seconds: int = 21600
    enabled: bool = True
    targets: list[ManifestTarget] = []


class AckResult(PersistedResponse):
    """Common shape for ack responses on collection_agents and telemetry agents."""

    acked_revision: int
    acked_at: str | None = None


class AgentConfigResponse(BaseModel):
    """Rendered config text (TOML) for a telemetry agent."""

    config: str
