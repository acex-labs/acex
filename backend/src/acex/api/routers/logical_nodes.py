import inspect
from typing import get_type_hints
from pydantic import BaseModel
from fastapi import APIRouter
from acex.constants import BASE_URL


def get_response_model(func):
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    plug = getattr(automation_engine.inventory, "logical_nodes")
    for cap in plug.capabilities:
        func = getattr(plug, cap)
        path = plug.path(cap)
        method = plug.http_verb(cap)
        response_model = get_response_model(func)

        router.add_api_route(
            f"/logical_nodes{path}",
            func,
            methods=[method],
            response_model=response_model,
            tags = ["Inventory"]
        )
    return router
