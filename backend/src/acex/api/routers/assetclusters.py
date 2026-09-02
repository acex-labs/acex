from acex.constants import BASE_URL
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    acm = automation_engine.inventory.asset_cluster_manager

    router.add_api_route("/asset_clusters", acm.create_cluster, methods=["POST"], tags=tags)
    router.add_api_route("/asset_clusters", acm.list_clusters, methods=["GET"], tags=tags)
    router.add_api_route("/asset_clusters/{id}", acm.get_cluster, methods=["GET"], tags=tags)
    router.add_api_route("/asset_clusters/{id}", acm.update_cluster, methods=["PATCH"], tags=tags)
    router.add_api_route("/asset_clusters/{id}", acm.delete_cluster, methods=["DELETE"], tags=tags)
    return router
