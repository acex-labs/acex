from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from acex.constants import BASE_URL


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    tam = automation_engine.inventory.telemetry_agent_manager

    router.add_api_route(
        "/telemetry_agents/",
        tam.create,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/",
        tam.list,
        methods=["GET"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}",
        tam.get,
        methods=["GET"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}",
        tam.update,
        methods=["PATCH"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}",
        tam.delete,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/nodes/{node_id}",
        tam.add_node,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/nodes/{node_id}",
        tam.remove_node,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/rules",
        tam.add_rule,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/rules/{rule_id}",
        tam.remove_rule,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/outputs",
        tam.add_output,
        methods=["POST"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/outputs/{output_id}",
        tam.update_output,
        methods=["PATCH"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/outputs/{output_id}",
        tam.remove_output,
        methods=["DELETE"],
        tags=tags,
    )
    router.add_api_route(
        "/telemetry_agents/{id}/config",
        tam.get_config,
        methods=["GET"],
        response_class=PlainTextResponse,
        tags=tags,
    )

    return router
