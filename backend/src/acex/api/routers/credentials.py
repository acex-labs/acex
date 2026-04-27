from fastapi import APIRouter

from acex.constants import BASE_URL


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    cm = automation_engine.credential_manager

    # Credential CRUD
    router.add_api_route("/credentials/", cm.create, methods=["POST"], tags=tags)
    router.add_api_route("/credentials/", cm.list, methods=["GET"], tags=tags)
    router.add_api_route("/credentials/{id}/secret", cm.get_secret, methods=["GET"], tags=tags)
    router.add_api_route("/credentials/{id}", cm.get, methods=["GET"], tags=tags)
    router.add_api_route("/credentials/{id}", cm.update, methods=["PATCH"], tags=tags)
    router.add_api_route("/credentials/{id}", cm.delete, methods=["DELETE"], tags=tags)

    # Node ↔ Credential mapping
    router.add_api_route("/nodes/{node_id}/credentials", cm.assign_to_node, methods=["POST"], tags=tags)
    router.add_api_route("/nodes/{node_id}/credentials", cm.list_node_credentials, methods=["GET"], tags=tags)
    router.add_api_route("/nodes/{node_id}/credentials/{credential_id}", cm.remove_node_credential, methods=["DELETE"], tags=tags)

    return router
