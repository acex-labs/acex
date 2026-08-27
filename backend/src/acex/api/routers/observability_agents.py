from acex.constants import BASE_URL
from acex_devkit.models.agent_manifest import AckResult
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/observability")
    tags = ["Observability"]

    tam = automation_engine.inventory.telemetry_agent_manager

    router.add_api_route(
        "/agents/",
        tam.create,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/",
        tam.query,
        methods=["GET"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}",
        tam.get,
        methods=["GET"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}",
        tam.update,
        methods=["PATCH"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}",
        tam.delete,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}/nodes/{node_id}",
        tam.add_node,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}/nodes/{node_id}",
        tam.remove_node,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}/rules",
        tam.add_rule,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}/rules/{rule_id}",
        tam.remove_rule,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}/config",
        tam.get_config,
        methods=["GET"],
        response_class=PlainTextResponse,
        tags=tags,
    )
    router.add_api_route(
        "/agents/{id}/ack",
        tam.ack,
        methods=["POST"],
        response_model=AckResult,
        tags=tags,
    )

    return router
