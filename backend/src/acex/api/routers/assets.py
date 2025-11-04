import inspect
import functools
from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.models import LogicalNode



def get_response_model(func):
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation



def create_router(automation_engine):

    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    # extract resource, function, endpoint_path, http verb
    plug = getattr(automation_engine.inventory, "assets")
    for cap in plug.capabilities:
        func = getattr(plug, cap)

        response_model = get_response_model(func)
        path = plug.path(cap)
        method = plug.http_verb(cap)
        router.add_api_route(
            f"/assets{path}",
            func,
            methods=[method],
            response_model=response_model,
            tags=tags
        )
    return router

