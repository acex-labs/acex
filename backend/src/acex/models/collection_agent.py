from acex_devkit.models.collection_agent import (
    CollectionAgentBase as CollectionAgentSchema,
)
from acex_devkit.models.collection_agent import (
    CollectionAgentCreate,
    CollectionAgentMatchRuleResponse,
    CollectionAgentResponse,
    CollectionAgentUpdate,
)
from acex_devkit.models.collection_agent import (
    CollectionAgentMatchRuleBase as CollectionAgentMatchRuleSchema,
)
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class CollectionAgentBase(CollectionAgentSchema, SQLModel):
    pass


class CollectionAgent(CollectionAgentBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    config_revision: int = Field(default=0)
    last_manifest_poll: str | None = None
    acked_revision: int = Field(default=0)
    acked_at: str | None = None


class CollectionAgentNodeLink(SQLModel, table=True):
    collection_agent_id: int = Field(foreign_key="collectionagent.id", primary_key=True)
    node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )


class CollectionAgentMatchRuleBase(CollectionAgentMatchRuleSchema, SQLModel):
    pass


class CollectionAgentMatchRuleCreate(CollectionAgentMatchRuleBase):
    pass


class CollectionAgentMatchRule(CollectionAgentMatchRuleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    collection_agent_id: int = Field(foreign_key="collectionagent.id")


class CollectionAgentAck(SQLModel):
    config_revision: int


__all__ = [
    "CollectionAgent",
    "CollectionAgentNodeLink",
    "CollectionAgentMatchRule",
    "CollectionAgentMatchRuleCreate",
    "CollectionAgentCreate",
    "CollectionAgentUpdate",
    "CollectionAgentAck",
    "CollectionAgentMatchRuleResponse",
    "CollectionAgentResponse",
]
