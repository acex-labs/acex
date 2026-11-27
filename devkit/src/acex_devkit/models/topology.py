from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TopologyNodeKind(StrEnum):
    """What a node of the graph stands for. Layers that map more than devices add their own kinds."""

    NODE_INSTANCE = "node_instance"
    UNMANAGED = "unmanaged"


class TopologyLayer(BaseModel):
    """A source of links. Several layers can be asked for at once and are drawn on top of each other."""

    key: str
    label: str
    description: str = ""


class TopologyNode(BaseModel):
    id: str
    kind: TopologyNodeKind
    label: str
    node_instance_id: int | None = None
    site: str | None = None
    regions: list[str] = []
    role: str | None = None
    in_scope: bool = False


class TopologyEndpoint(BaseModel):
    node: str
    interface: str = ""


class TopologyLink(BaseModel):
    """One link of one layer. A pair of nodes linked on several layers has one link per layer."""

    id: str
    layer: str
    a: TopologyEndpoint
    b: TopologyEndpoint
    attributes: dict[str, Any] = {}


class TopologyGraph(BaseModel):
    layers: list[str] = []
    nodes: list[TopologyNode] = []
    links: list[TopologyLink] = []


class TopologyPosition(BaseModel):
    """Where an item lies in a container of the shared topology layout, relative to the container's origin.

    Containers are `site:<name>` (the nodes of a site), `region:<name>` (the sites of a region), and `site-boxes`,
    `region-boxes` and `regions` (the boxes or cards around them). An item is a node id or a site or region name.
    """

    container: str
    item: str
    x: float
    y: float


class TopologyPositionResponse(TopologyPosition):
    updated_by: str | None = None
    updated_at: datetime | None = None
