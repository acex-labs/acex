from datetime import datetime, timezone

from acex_devkit.models.lldp_neighbor import (
    LldpNeighborBase as LldpNeighborSchema,
)
from acex_devkit.models.lldp_neighbor import (
    LldpNeighborEntry,
    LldpNeighborResponse,
    LldpNeighborUpload,
)
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class LldpNeighbor(LldpNeighborSchema, SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    node_instance_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    remote_node_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    hash: str = Field(index=True)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


__all__ = [
    "LldpNeighbor",
    "LldpNeighborEntry",
    "LldpNeighborUpload",
    "LldpNeighborResponse",
]
