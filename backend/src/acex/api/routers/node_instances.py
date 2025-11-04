import inspect
import functools
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from typing import Callable, Any, Optional

from acex.constants import BASE_URL


def get_response_model(func):
    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation

def get_request_model(func: Callable) -> Optional[type]:
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        param_type = type_hints.get(name)
        if param_type and isinstance(param_type, type) and issubclass(param_type, BaseModel):
            return param_type
    return None


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    plug = getattr(automation_engine.inventory, "node_instances")
    for cap in plug.capabilities:
        func = getattr(plug, cap)
        path = plug.path(cap)
        method = plug.http_verb(cap)
        response_model = get_response_model(func)

        router.add_api_route(
            f"/node_instances{path}",
            func,
            methods=[method],
            response_model=response_model,
            tags=tags
        )

    router.add_api_route(
        "/node_instances/{id}/config",
        automation_engine.inventory.node_instances.get_rendered_config,
        methods=["GET"],
        response_class=PlainTextResponse,
        tags=tags
    )

    return router




