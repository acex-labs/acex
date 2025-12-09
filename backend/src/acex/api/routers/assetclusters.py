import inspect
import functools
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse
from typing import Callable, Any, Optional

from acex.models import StoredDeviceConfig
from acex.constants import BASE_URL



def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/assetclusters")
    tags = ["Inventory"]

    acm = automation_engine.inventory.asset_cluster_manager

    router.add_api_route(
        "/asset_clusters/",
        acm.create_cluster,
        methods=["POST"],
        tags=tags
    )
    router.add_api_route(
        "/asset_clusters/",
        acm.list_clusters,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/asset_clusters/{cluster_id}",
        acm.get_cluster,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/asset_clusters/",
        acm.update_cluster_assets,
        methods=["PATCH"],
        tags=tags
    )
    return router




