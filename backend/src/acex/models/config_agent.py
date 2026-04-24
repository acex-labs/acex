from typing import Optional
from sqlmodel import SQLModel, Field


class ConfigAgentBase(SQLModel):
    name: str
    description: Optional[str] = None
    interval_seconds: int = 21600
    enabled: bool = True


class ConfigAgent(ConfigAgentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    config_revision: int = Field(default=0)
    last_manifest_poll: Optional[str] = None


class ConfigAgentNodeLink(SQLModel, table=True):
    config_agent_id: int = Field(foreign_key="configagent.id", primary_key=True)
    node_id: int = Field(foreign_key="node.id", primary_key=True)


class ConfigAgentMatchRuleBase(SQLModel):
    site: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class ConfigAgentMatchRule(ConfigAgentMatchRuleBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    config_agent_id: int = Field(foreign_key="configagent.id")


class ConfigAgentMatchRuleCreate(ConfigAgentMatchRuleBase):
    pass


class ConfigAgentMatchRuleResponse(ConfigAgentMatchRuleBase):
    id: int


class ConfigAgentCreate(SQLModel):
    name: str
    description: Optional[str] = None
    interval_seconds: int = 21600
    enabled: bool = True


class ConfigAgentUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: Optional[bool] = None


class ConfigAgentResponse(ConfigAgentBase):
    id: int
    config_revision: int = 0
    last_manifest_poll: Optional[str] = None
    nodes: list[int] = []
    rules: list[ConfigAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []
