from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class NodeCollectionState(SQLModel, table=True):
    __tablename__ = "node_collection_state"

    node_id: int = Field(
        sa_column=Column(Integer, ForeignKey("node.id", ondelete="CASCADE"), primary_key=True),
    )
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    failing_since: datetime | None = None
    consecutive_failures: int = Field(default=0)
    category: str | None = None
    message: str | None = None
    agent_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("collectionagent.id", ondelete="SET NULL"), nullable=True),
    )
