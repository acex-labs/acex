from acex.config_diff import DiffLogicalNode
from acex.constants import BASE_URL
from fastapi import APIRouter


def hello():
    return "hello"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/health")
    tags = ["Health"]
    dcm = automation_engine.device_config_manager
    differ = DiffLogicalNode(automation_engine.inventory, dcm)

    router.add_api_route(
        "/node_instance/{node_instance_id}", differ.compliance_check_node_instance, methods=["GET"], tags=tags
    )

    router.add_api_route("/site/{site_name}", differ.compliance_check_site, methods=["GET"], tags=tags)

    return router
