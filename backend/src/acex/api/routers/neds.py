from acex.constants import BASE_URL
from acex.models.ned import Ned
from acex.plugins.neds.manager import NEDManager
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

nm = NEDManager()
# nm.download_and_install_neds_in_specs()
nm.load_drivers()


def list_neds():
    neds = nm.list_drivers()
    return neds


def get_ned(ned_id: str):
    ned = nm.get_driver_info(ned_id)
    return ned


def download_ned(filename: str):
    # Only wheels the backend built itself: the name never becomes a path.
    path = nm.wheel_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Driver not found")

    return FileResponse(path, filename=filename)


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/neds")
    tags = ["Inventory"]
    router.add_api_route("", list_neds, methods=["GET"], tags=tags, response_model=list[Ned])
    router.add_api_route("/{ned_id}", get_ned, methods=["GET"], tags=tags, response_model=Ned)
    router.add_api_route("/download/{filename}", download_ned, methods=["GET"], tags=tags)

    return router
