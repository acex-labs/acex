
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from acex.constants import BASE_URL


def create_router(automation_engine):

    if not hasattr(automation_engine, "ai_ops_manager"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/ai_ops")
    tags = ["AI Operations"]

    aiom = automation_engine.ai_ops_manager
    router.add_api_route(
        "/ai/ask/",
        aiom.ask,
        methods=["GET"],
        tags=tags
    )

    return router




