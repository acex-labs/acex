from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class TopologyPositionRow(SQLModel, table=True):
    """Where one item lies in one container of the shared topology layout. See `TopologyPosition`."""

    __tablename__ = "topology_position"
    __table_args__ = (UniqueConstraint("container", "item", name="uq_topology_position_container_item"),)

    id: int | None = Field(default=None, primary_key=True)
    container: str = Field(index=True)
    item: str
    x: float
    y: float
    updated_by: str | None = None
    updated_at: datetime | None = None


__all__ = ["TopologyPositionRow"]
