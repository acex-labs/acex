import inspect
import functools
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from typing import Callable, Any, Optional

from acex.models import ManagementConnection
from acex.constants import BASE_URL


def get_stuff(): return "hej"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    manager = automation_engine.mgmt_con_manager

    router.add_api_route(
        "/management_connections/{id}",
        manager.create_connection,
        methods=["POST"],
        tags=tags
    )
    router.add_api_route(
        "/management_connections/",
        manager.list_connections,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/management_connections/{id}",
        manager.get_connection,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/management_connections/{id}",
        manager.delete_connection,
        methods=["DELETE"],
        tags=tags
    )
    return router




