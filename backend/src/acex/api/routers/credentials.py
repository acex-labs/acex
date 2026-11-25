from acex.api import auth as _auth
from acex.constants import BASE_URL
from fastapi import APIRouter, Depends


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    cm = automation_engine.credential_manager

    # Credential CRUD
    router.add_api_route("/credentials", cm.create, methods=["POST"], tags=tags)
    router.add_api_route("/credentials", cm.query, methods=["GET"], tags=tags)
    # The one route that returns a login in the clear: it needs a role when ACEX_AUTHZ_MODE says so.
    router.add_api_route(
        "/credentials/{id}/secret",
        cm.get_secret,
        methods=["GET"],
        tags=tags,
        dependencies=[Depends(_auth.require_role("admin", "service"))],
        description=(
            "The stored login in the clear, from the database or from Vault. With ACEX_AUTHZ_MODE=enforce the token "
            "must list the admin or the service role."
        ),
    )
    router.add_api_route("/credentials/{id}", cm.get, methods=["GET"], tags=tags)
    router.add_api_route("/credentials/{id}", cm.update, methods=["PATCH"], tags=tags)
    router.add_api_route("/credentials/{id}", cm.delete, methods=["DELETE"], tags=tags)

    # Node ↔ Credential mapping
    router.add_api_route("/nodes/{node_id}/credentials", cm.assign_to_node, methods=["POST"], tags=tags)
    # Deprecated: credentials are joined into GET /node_instances/{id}.
    router.add_api_route(
        "/nodes/{node_id}/credentials", cm.list_node_credentials, methods=["GET"], tags=tags, deprecated=True
    )
    router.add_api_route(
        "/nodes/{node_id}/credentials/{credential_id}", cm.remove_node_credential, methods=["DELETE"], tags=tags
    )

    # Site ↔ Credential mapping
    router.add_api_route("/sites/{site_name}/credentials", cm.assign_to_site, methods=["POST"], tags=tags)
    router.add_api_route("/sites/{site_name}/credentials", cm.list_site_credentials, methods=["GET"], tags=tags)
    router.add_api_route(
        "/sites/{site_name}/credentials/{credential_id}", cm.remove_site_credential, methods=["DELETE"], tags=tags
    )

    # SNMP community resolution traceability
    router.add_api_route("/nodes/{node_id}/snmp-community-source", cm.get_snmp_resolution, methods=["GET"], tags=tags)

    return router
