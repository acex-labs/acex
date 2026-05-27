import inspect
from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.models.regions import SiteRegionAssignment


def get_response_model(func):
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation


def create_router(automation_engine):

    if not hasattr(automation_engine.inventory, "regions"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    plug = getattr(automation_engine.inventory, "regions")
    for cap in plug.capabilities:
        func = getattr(plug, cap)
        response_model = get_response_model(func)
        path = plug.path(cap)
        method = plug.http_verb(cap)
        router.add_api_route(
            f"/regions{path}",
            func,
            methods=[method],
            response_model=response_model,
            tags=tags
        )

    ram = automation_engine.inventory.region_assignment_manager

    router.add_api_route(
        "/region_assignments/",
        ram.create_assignment,
        methods=["POST"],
        response_model=SiteRegionAssignment,
        tags=tags
    )
    router.add_api_route(
        "/region_assignments/",
        ram.list_assignments,
        methods=["GET"],
        response_model=list[SiteRegionAssignment],
        tags=tags
    )
    router.add_api_route(
        "/region_assignments/{id}",
        ram.delete_assignment,
        methods=["DELETE"],
        tags=tags
    )

    return router
