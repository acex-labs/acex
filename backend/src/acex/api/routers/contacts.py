import inspect
from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.models.contacts import ContactAssignment


def get_response_model(func):
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation


def create_router(automation_engine):

    if not hasattr(automation_engine.inventory, "contacts"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    # Contact CRUD
    plug = getattr(automation_engine.inventory, "contacts")
    for cap in plug.capabilities:
        func = getattr(plug, cap)
        response_model = get_response_model(func)
        path = plug.path(cap)
        method = plug.http_verb(cap)
        router.add_api_route(
            f"/contacts{path}",
            func,
            methods=[method],
            response_model=response_model,
            tags=tags
        )

    # Contact Assignments
    cam = automation_engine.inventory.contact_assignment_manager

    router.add_api_route(
        "/contact_assignments/",
        cam.create_assignment,
        methods=["POST"],
        response_model=ContactAssignment,
        tags=tags
    )
    router.add_api_route(
        "/contact_assignments/",
        cam.list_assignments,
        methods=["GET"],
        response_model=list[ContactAssignment],
        tags=tags
    )
    router.add_api_route(
        "/contact_assignments/{id}",
        cam.delete_assignment,
        methods=["DELETE"],
        tags=tags
    )

    return router
