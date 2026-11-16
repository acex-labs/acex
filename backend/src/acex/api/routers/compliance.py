from acex.compliance import ComplianceService
from acex.constants import BASE_URL
from fastapi import APIRouter


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/compliance")
    tags = ["Compliance"]

    compliance = ComplianceService(
        automation_engine.inventory, automation_engine.device_config_manager, automation_engine.software_policies
    )
    # The API starts measuring the installation in the background when it starts.
    automation_engine.compliance = compliance

    router.add_api_route("", compliance.latest_overview, methods=["GET"], tags=tags)
    router.add_api_route("/nodes/{node_instance_id}", compliance.node, methods=["GET"], tags=tags)
    router.add_api_route("/sites/{site_name}", compliance.site, methods=["GET"], tags=tags)
    router.add_api_route("/regions/{region_name}", compliance.region, methods=["GET"], tags=tags)

    return router
