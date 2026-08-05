from acex.constants import BASE_URL
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations")
    tags = ["Operations"]

    dcm = automation_engine.device_config_manager

    router.add_api_route("/configuration/changes", dcm.list_changes, methods=["GET"], tags=tags)

    return router
