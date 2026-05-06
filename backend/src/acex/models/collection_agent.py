from typing import Optional
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import SQLModel, Field


class CollectionAgentBase(SQLModel):
    name: str
    description: Optional[str] = None
    interval_seconds: int = 21600
    enabled: bool = True


class CollectionAgent(CollectionAgentBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    config_revision: int = Field(default=0)
    last_manifest_poll: Optional[str] = None
    acked_revision: int = Field(default=0)
    acked_at: Optional[str] = None


class CollectionAgentNodeLink(SQLModel, table=True):
    collection_agent_id: int = Field(foreign_key="collectionagent.id", primary_key=True)
    node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


class CollectionAgentMatchRuleBase(SQLModel):
    site: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None


class CollectionAgentMatchRule(CollectionAgentMatchRuleBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_agent_id: int = Field(foreign_key="collectionagent.id")


class CollectionAgentMatchRuleCreate(CollectionAgentMatchRuleBase):
    pass


class CollectionAgentMatchRuleResponse(CollectionAgentMatchRuleBase):
    id: int


class CollectionAgentCreate(SQLModel):
    name: str
    description: Optional[str] = None
    interval_seconds: int = 21600
    enabled: bool = True


class CollectionAgentUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: Optional[bool] = None


class CollectionAgentAck(SQLModel):
    config_revision: int


class CollectionAgentResponse(CollectionAgentBase):
    id: int
    config_revision: int = 0
    last_manifest_poll: Optional[str] = None
    acked_revision: int = 0
    acked_at: Optional[str] = None
    nodes: list[int] = []
    rules: list[CollectionAgentMatchRuleResponse] = []
    resolved_nodes: list[int] = []
