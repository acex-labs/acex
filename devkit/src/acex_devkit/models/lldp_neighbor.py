from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from acex_devkit.models.base import PersistedResponse


class LldpNeighborBase(BaseModel):
    local_interface: str
    remote_device: str
    remote_interface: str = ""
    discovery_protocol: str = "lldp"


class LldpNeighborEntry(LldpNeighborBase):
    pass


class LldpNeighborUpload(BaseModel):
    node_instance_id: int
    neighbors: list[LldpNeighborEntry]


class LldpNeighborResponse(PersistedResponse, LldpNeighborBase):
    node_instance_id: int
    remote_node_id: Optional[int] = None
    collected_at: datetime
