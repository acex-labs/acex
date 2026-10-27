from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class CollectionAgentBase(BaseModel):
    name: str
    description: str | None = None
    interval_seconds: int = 21600
    enabled: bool = True


class CollectionAgentMatchRuleBase(BaseModel):
    region: str | None = None
    site: str | None = None
    vendor: str | None = None
    os: str | None = None
    admin_status: str | None = None
    provision_status: str | None = None
    role: str | None = None


class CollectionAgentMatchRuleResponse(PersistedResponse, CollectionAgentMatchRuleBase):
    pass


class CollectionAgentCreate(CollectionAgentBase):
    pass


class CollectionAgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    interval_seconds: int | None = None
    enabled: bool | None = None


class CollectionAgentResponse(PersistedResponse, CollectionAgentBase):
    config_revision: int = 0
    last_manifest_poll: str | None = None
    acked_revision: int = 0
    acked_at: str | None = None
    # Reported by the agent in its last ack; None until it has sent them.
    agent_version: str | None = None
    build_id: str | None = None
    build_ref: str | None = None
    nodes: list[int] = []
    rules: list[CollectionAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []


class CollectionAgentAck(BaseModel):
    config_revision: int
    # What the agent runs: its package version, the commit its image was built from and the branch that build
    # ran on (dev for development images). All optional, so an agent that does not report them still acks.
    agent_version: str | None = None
    build_id: str | None = None
    build_ref: str | None = None


class CollectionAgentMatchRuleCreate(CollectionAgentMatchRuleBase):
    pass
