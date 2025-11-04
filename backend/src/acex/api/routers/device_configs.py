import inspect
import functools
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from typing import Callable, Any, Optional

from acex.models import StoredDeviceConfig
from acex.constants import BASE_URL



def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations")
    tags = ["Operations"]

    dcm = automation_engine.device_config_manager
    router.add_api_route(
        "/device_configs/{node_instance_id}",
        dcm.list_config_hashes,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/device_configs/{node_instance_id}/latest",
        dcm.get_latest_config,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/device_configs/{node_instance_id}/{hash}",
        dcm.get_config_by_hash,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/device_configs/",
        dcm.upload_config,
        methods=["POST"],
        tags=tags
    )
    return router




