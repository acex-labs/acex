from fastapi import APIRouter

from acex.constants import BASE_URL


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    cam = automation_engine.inventory.collection_agent_manager

    router.add_api_route("/collection_agents/", cam.create, methods=["POST"], tags=tags)
    router.add_api_route("/collection_agents/", cam.list, methods=["GET"], tags=tags)
    router.add_api_route("/collection_agents/{id}", cam.get, methods=["GET"], tags=tags)
    router.add_api_route("/collection_agents/{id}", cam.update, methods=["PATCH"], tags=tags)
    router.add_api_route("/collection_agents/{id}", cam.delete, methods=["DELETE"], tags=tags)

    router.add_api_route("/collection_agents/{id}/nodes/{node_id}", cam.add_node, methods=["POST"], tags=tags)
    router.add_api_route("/collection_agents/{id}/nodes/{node_id}", cam.remove_node, methods=["DELETE"], tags=tags)

    router.add_api_route("/collection_agents/{id}/rules", cam.add_rule, methods=["POST"], tags=tags)
    router.add_api_route("/collection_agents/{id}/rules/{rule_id}", cam.remove_rule, methods=["DELETE"], tags=tags)

    router.add_api_route("/collection_agents/{id}/ack", cam.ack_manifest, methods=["POST"], tags=tags)
    router.add_api_route("/collection_agents/{id}/manifest", cam.get_manifest, methods=["GET"], tags=tags)

    return router
