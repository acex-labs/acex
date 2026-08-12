from datetime import datetime

from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class LldpUploadResult(BaseModel):
    """Result of an LLDP neighbor upload."""

    uploaded: int = 0
    deduplicated: int = 0
    re_resolved: int = 0
    errors: list[str] = []


class LldpTopologyNode(BaseModel):
    id: int | str
    label: str
    in_inventory: bool


class LldpTopologyEdge(BaseModel):
    source: int | str
    target: int | str
    source_interface: str = ""
    target_interface: str = ""
    discovery_protocol: str = "lldp"


class LldpTopology(BaseModel):
    nodes: list[LldpTopologyNode] = []
    edges: list[LldpTopologyEdge] = []


class LldpNeighborListItem(PersistedResponse):
    """Compact list shape for `GET /operations/lldp_neighbors/{node_instance_id}`.

    Mirrors LldpNeighborResponse but flattened for list contexts.
    """

    node_instance_id: int
    local_interface: str
    remote_device: str
    remote_interface: str = ""
    discovery_protocol: str = "lldp"
    remote_node_id: int | None = None
    collected_at: datetime
