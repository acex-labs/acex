
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from acex.constants import BASE_URL


def create_router(automation_engine):

    # TODO: Fixa toggle så att ai ops bara finns om klient och api nyckel finns
    if "AI OPS" == False:
        return None

    router = APIRouter(prefix=f"{BASE_URL}/ai_ops")
    tags = ["AI Operations"]

    dcm = automation_engine.device_config_manager
    router.add_api_route(
        "/device_configs/{node_instance_id}",
        dcm.list_config_hashes,
        methods=["GET"],
        tags=tags
    )

    return router




