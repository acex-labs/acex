from importlib.metadata import version, distributions, entry_points

import platform
import os

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

    def health():
        return {"status": "ok", "version": version("acex")}

    router.add_api_route("", health, methods=["GET"], tags=tags)

    def about():
        packages = {
            dist.metadata["Name"]: dist.version
            for dist in distributions()
            if dist.metadata["Name"] and dist.metadata["Name"].lower().startswith("acex")
        }
        drivers = [
            {
                "name": ep.value.split(":")[-1],
                "package": ep.dist.name,
                "version": ep.dist.version,
            }
            for ep in entry_points(group="acex.neds")
        ]
        return {
            "version": version("acex"),
            "build_id": os.environ.get("ACEX_BUILD_ID") or None,
            "python": platform.python_version(),
            "packages": dict(sorted(packages.items())),
            "drivers": sorted(drivers, key=lambda d: d["name"]),
        }
    router.add_api_route("/about", about, methods=["GET"], tags=tags)

    return router
