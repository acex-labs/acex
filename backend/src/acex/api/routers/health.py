import os
import platform
from importlib.metadata import distributions, entry_points, version

from acex.constants import BASE_URL
from fastapi import APIRouter


def hello():
    return "hello"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/health")
    tags = ["Health"]

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
            "build_ref": os.environ.get("ACEX_BUILD_REF") or None,
            "python": platform.python_version(),
            "packages": dict(sorted(packages.items())),
            "drivers": sorted(drivers, key=lambda d: d["name"]),
        }

    router.add_api_route("/about", about, methods=["GET"], tags=tags)

    return router
