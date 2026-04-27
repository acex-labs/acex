from fastapi import APIRouter

from acex.constants import BASE_URL


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations")
    tags = ["Operations"]

    lm = automation_engine.lldp_neighbor_manager

    router.add_api_route("/lldp_neighbors/", lm.upload_neighbors, methods=["POST"], tags=tags)
    router.add_api_route("/lldp_neighbors/topology", lm.get_topology, methods=["GET"], tags=tags)
    router.add_api_route("/lldp_neighbors/by-site/{site}", lm.get_neighbors_by_site, methods=["GET"], tags=tags)
    router.add_api_route("/lldp_neighbors/{node_instance_id}", lm.get_neighbors, methods=["GET"], tags=tags)
    router.add_api_route("/lldp_neighbors/{node_instance_id}/reverse", lm.get_reverse_neighbors, methods=["GET"], tags=tags)

    return router
