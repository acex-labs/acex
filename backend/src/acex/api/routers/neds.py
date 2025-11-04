
from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.plugins.neds.manager import NEDManager

nm = NEDManager()

def list_neds():
    neds = nm.list_drivers()
    return neds

def get_ned(driver_name: str, version: str = ""):
    ned = nm.get_driver(driver_name)

    return ned

def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/neds")
    tags = ["Inventory"]
    router.add_api_route(
        "/",
        list_neds,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/{ned_id}",
        get_ned,
        methods=["GET"],
        tags=tags
    )

    return router


