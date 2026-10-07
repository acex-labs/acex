import logging
from datetime import UTC, datetime

from acex.constants import BASE_URL
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

logger = logging.getLogger("acex.api.ztp")
# No root logging config in the app; without this, INFO is dropped.
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def render_cisco_iosxe():
    content = """#!/usr/bin/env python
import cli

print("*** ZTP: applying base configuration ***")

cli.configurep(
    [
        "hostname acex-ztp-init-device",
        "ip domain name example.com",
        "username cisco privilege 15 secret 0 Cisco123",
        "crypto key generate rsa modulus 2048",
        "ip ssh version 2",
        "line vty 0 15",
        "transport input ssh",
        "login local",
        "end",
    ]
)

cli.executep("copy running-config startup-config")
print("*** ZTP: done ***")
"""
    return content


CONFIG_GENERATORS = {"cisco_iosxe": render_cisco_iosxe}


def collect_request_metadata(request: Request, os_type: str) -> dict:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "os_type": os_type,
        "client_ip": request.client.host if request.client else None,
        "client_port": request.client.port if request.client else None,
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "x_real_ip": request.headers.get("x-real-ip"),
        "user_agent": request.headers.get("user-agent"),
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
    }


async def get_ztp_config(
    os_type: str,
    request: Request,
):
    metadata = collect_request_metadata(request, os_type)
    logger.info("ZTP script requested: %s", metadata)

    generator = CONFIG_GENERATORS.get(os_type)
    if generator is None:
        raise HTTPException(status_code=404, detail="Unsupported os type")

    # Generera innehåll dynamiskt
    content = generator()

    return Response(
        content=content,
        media_type="application/x-python",
        headers={"Content-Disposition": "attachment; filename=ztp.py"},
    )


def list_os_types():
    return list(CONFIG_GENERATORS.keys())


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/ztp")
    tags = ["Ztp"]
    router.add_api_route("", list_os_types, methods=["GET"], tags=tags, response_model=list[str])
    router.add_api_route("/init_config/{os_type}/ztp.py", get_ztp_config, methods=["GET"], tags=tags)
    return router
