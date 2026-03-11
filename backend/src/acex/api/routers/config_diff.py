from fastapi import APIRouter, Response
from typing import Callable, Any, Optional
from acex.constants import BASE_URL
from acex.config_diff import DiffLogicalNode


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations")
    tags = ["Operations"]
    dcm = automation_engine.device_config_manager
    differ = DiffLogicalNode(automation_engine.inventory, dcm)


    
    router.add_api_route(
        "/diff/{node_instance_id}",
        differ.diff,
        methods=["GET"],
        tags=tags
    )
    return router




