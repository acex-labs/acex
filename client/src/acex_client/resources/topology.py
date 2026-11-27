"""Topology — `/topology`: links over one or more layers, for the whole network or some regions or a site."""

from __future__ import annotations

from acex_devkit.models.topology import TopologyGraph, TopologyLayer, TopologyPosition, TopologyPositionResponse

from acex_client.resources.base import ActionMixin, Resource, action


class Topology(Resource, ActionMixin):
    """`graph()` the topology of the named layers, all of them by default; `layers()` the layers there are.

    `positions()`, `save_positions()` and `reset_positions()` read and change the shared layout of the topology page.
    """

    path = "/topology"
    response_model = TopologyGraph  # type: ignore
    list_model = TopologyGraph  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "")
    def graph(
        self,
        layers: list[str] | None = None,
        region: list[str] | None = None,
        site: str | None = None,
    ) -> TopologyGraph: ...

    @action("GET", "layers")
    def layers(self) -> list[TopologyLayer]: ...

    @action("GET", "positions")
    def positions(self, container: list[str] | None = None) -> list[TopologyPositionResponse]: ...

    @action("PUT", "positions")
    def save_positions(self, payload: list[TopologyPosition]) -> list[TopologyPositionResponse]: ...

    @action("DELETE", "positions")
    def reset_positions(self, container: list[str], item: list[str] | None = None) -> None: ...
