from fastapi import APIRouter
from acex.constants import BASE_URL
from acex.config_diff import DiffLogicalNode


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/operations")
    tags = ["Operations"]

    dcm = automation_engine.device_config_manager
    differ = DiffLogicalNode(automation_engine.inventory, dcm)

    router.add_api_route(
        "/compliance/{node_instance_id}",
        differ.compliance_check_node_instance,
        methods=["GET"],
        tags=tags
    )
    router.add_api_route(
        "/compliance/site/{site_name}",
        differ.compliance_check_site,
        methods=["GET"],
        tags=tags
    )

    return router
