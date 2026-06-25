from pydantic import BaseModel
from typing import Optional

from acex_devkit.models.base import PersistedResponse


class CollectionAgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    interval_seconds: int = 21600
    enabled: bool = True


class CollectionAgentMatchRuleBase(BaseModel):
    region: Optional[str] = None
    site: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class CollectionAgentMatchRuleResponse(PersistedResponse, CollectionAgentMatchRuleBase):
    pass


class CollectionAgentCreate(CollectionAgentBase):
    pass


class CollectionAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: Optional[bool] = None


class CollectionAgentResponse(PersistedResponse, CollectionAgentBase):
    config_revision: int = 0
    last_manifest_poll: Optional[str] = None
    acked_revision: int = 0
    acked_at: Optional[str] = None
    nodes: list[int] = []
    rules: list[CollectionAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []
