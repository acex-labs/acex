from typing import Annotated

from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex_devkit.models.topology import TopologyGraph, TopologyLayer, TopologyPosition, TopologyPositionResponse
from fastapi import APIRouter, Depends, Query, status


def _editor(user: dict) -> str:
    """Who changed it: a readable name if the token has one, else its subject."""
    return user.get("preferred_username") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/topology", tags=["Topology"])

    topology = automation_engine.topology
    positions = automation_engine.topology_positions

    router.add_api_route("/layers", topology.layers, methods=["GET"], response_model=list[TopologyLayer])
    router.add_api_route("/positions", positions.query, methods=["GET"], response_model=list[TopologyPositionResponse])
    router.add_api_route("", topology.graph, methods=["GET"], response_model=TopologyGraph)

    @router.put("/positions", response_model=list[TopologyPositionResponse])
    def save_positions(
        payload: list[TopologyPosition],
        user: dict = Depends(_auth.get_current_user),  # noqa: B008
    ):
        return positions.save(payload, updated_by=_editor(user))

    @router.delete("/positions", status_code=status.HTTP_204_NO_CONTENT)
    def reset_positions(
        container: Annotated[list[str], Query(min_length=1)],
        item: Annotated[list[str] | None, Query()] = None,
    ):
        positions.reset(container, item)

    return router
