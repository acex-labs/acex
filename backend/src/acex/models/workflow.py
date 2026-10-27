from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

_JSON = JSON().with_variant(JSONB(), "postgresql")


class WorkflowRow(SQLModel, table=True):
    """A workflow: its steps on a graph from start to end."""

    __tablename__ = "workflow"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    #: A `WorkflowGraph`, its steps included.
    graph: dict = Field(sa_column=Column(_JSON, nullable=False))
    max_rounds: int = 100
    created_by: str
    updated_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = ["WorkflowRow"]
