
from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.plugins.neds.manager import NEDManager
from fastapi.responses import FileResponse
from fastapi import HTTPException


nm = NEDManager()


def list_neds():
    neds = nm.list_drivers()
    return neds

def get_ned(ned_id: str):
    ned = nm.get_driver_info(ned_id)
    return ned

def download_ned(ned_id: str):
    ned_path = nm.driver_download_path(ned_id)
    if ned_path is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    filename = ned_path.split('/')[-1]
    return FileResponse(ned_path, filename=filename)

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
    router.add_api_route(
        "/{ned_id}/download",
        download_ned,
        methods=["GET"],
        tags=tags
    )

    return router


