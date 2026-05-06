from typing import Optional
from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import SQLModel, Field


class LldpNeighbor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_instance_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    local_interface: str
    remote_device: str
    remote_interface: str = ""
    remote_node_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("node.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    discovery_protocol: str = "lldp"
    hash: str = Field(index=True)
    collected_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class LldpNeighborEntry(SQLModel):
    local_interface: str
    remote_device: str
    remote_interface: str = ""
    discovery_protocol: str = "lldp"


class LldpNeighborUpload(SQLModel):
    node_instance_id: int
    neighbors: list[LldpNeighborEntry]


class LldpNeighborResponse(SQLModel):
    id: int
    node_instance_id: int
    local_interface: str
    remote_device: str
    remote_interface: str
    remote_node_id: Optional[int] = None
    discovery_protocol: str
    collected_at: datetime
