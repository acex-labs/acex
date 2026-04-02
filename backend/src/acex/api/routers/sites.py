import inspect
from fastapi import APIRouter
from acex.constants import BASE_URL


def get_response_model(func):
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation


def create_router(automation_engine):

    if not hasattr(automation_engine.inventory, "sites"):
        return None

    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    plug = getattr(automation_engine.inventory, "sites")
    for cap in plug.capabilities:
        func = getattr(plug, cap)

        response_model = get_response_model(func)
        path = plug.path(cap)
        method = plug.http_verb(cap)
        router.add_api_route(
            f"/sites{path}",
            func,
            methods=[method],
            response_model=response_model,
            tags=tags
        )
    return router
