import base64
from datetime import datetime

from acex.config_diff import DiffLogicalNode
from acex.constants import BASE_URL
from acex.device_configs.device_config_manager import ConfigOutput
from acex.models.device_config import DeviceConfig
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel


def get_response_model(func):
    import inspect

    sig = inspect.signature(func)
    return_annotation = sig.return_annotation
    if return_annotation is inspect.Signature.empty:
        return None
    return return_annotation


class DeviceConfigUpload(BaseModel):
    content: str


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/inventory")
    tags = ["Inventory"]

    plug = automation_engine.inventory.node_instances
    dcm = automation_engine.device_config_manager
    differ = DiffLogicalNode(automation_engine.inventory, dcm)

    # CRUD
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
            response_model_exclude_none=True,
            tags=tags,
        )

    # Configuration — desired (rendered text via NED)
    router.add_api_route(
        "/node_instances/{id}/configuration/desired",
        plug.get_rendered_config,
        methods=["GET"],
        response_class=PlainTextResponse,
        tags=tags,
    )

    # Configuration — observed snapshots
    async def list_observed(id: str, point_in_time: datetime = None, limit: int = 100):
        return dcm.list_config_hashes(node_instance_id=id, point_in_time=point_in_time, limit=limit)

    async def upload_observed(id: str, payload: DeviceConfigUpload):
        return await dcm.upload_config(DeviceConfig(node_instance_id=id, content=payload.content))

    async def get_observed_latest(id: str, output: ConfigOutput = ConfigOutput.RENDERED):
        result = await dcm.get_latest_config(node_instance_id=id, output=output)
        if result and isinstance(result.content, str):
            result.content = base64.b64encode(result.content.encode()).decode()
        return result

    async def get_observed_by_id(id: str, config_id: int):
        result = dcm.get_config_by_id(node_instance_id=id, config_id=config_id)
        if result and isinstance(result.content, str):
            result.content = base64.b64encode(result.content.encode()).decode()
        return result

    async def diff_observed(id: str, a: int, b: int):
        return dcm.diff_configs(node_instance_id=id, a=a, b=b)

    async def intent_diff(id: str):
        return await differ.diff(node_instance_id=id)

    router.add_api_route("/node_instances/{id}/configuration/observed/", list_observed, methods=["GET"], tags=tags)
    router.add_api_route("/node_instances/{id}/configuration/observed/", upload_observed, methods=["POST"], tags=tags)
    router.add_api_route(
        "/node_instances/{id}/configuration/observed/latest", get_observed_latest, methods=["GET"], tags=tags
    )
    router.add_api_route("/node_instances/{id}/configuration/observed/diff", diff_observed, methods=["GET"], tags=tags)
    router.add_api_route(
        "/node_instances/{id}/configuration/observed/{config_id}", get_observed_by_id, methods=["GET"], tags=tags
    )
    router.add_api_route("/node_instances/{id}/configuration/intent_diff", intent_diff, methods=["GET"], tags=tags)

    return router
