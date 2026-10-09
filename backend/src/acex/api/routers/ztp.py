import logging

from acex.constants import BASE_URL
from acex.jobs import ZTP_DISCOVER
from acex.messaging import MessagingNotConfigured
from acex_devkit.models.ztp import ZtpMethod
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

logger = logging.getLogger("acex.api.ztp")


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


def _start_discovery(jobs, ip: str, method: ZtpMethod) -> None:
    """Queue discovery of a device that fetched its bootstrap.

    The device gets its bootstrap whatever happens here: a broker that is off
    or down must not stop a switch from coming up.
    """
    try:
        job = jobs.enqueue(ZTP_DISCOVER.name, {"ip": ip, "method": method}, created_by="system")
    except MessagingNotConfigured:
        logger.warning(f"ZTP: {ip} fetched its {method} bootstrap, but RabbitMQ is off; no discovery queued")
    except Exception:
        logger.exception(f"ZTP: {ip} fetched its {method} bootstrap, but discovery could not be queued")
    else:
        logger.info(f"ZTP: {ip} fetched its {method} bootstrap; discovery job {job.id} queued")


def list_os_types():
    return list(CONFIG_GENERATORS.keys())


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/ztp")
    tags = ["Ztp"]

    async def get_ztp_config(request: Request):
        # generator = CONFIG_GENERATORS.get(os_type)
        # if generator is None:
        #     raise HTTPException(status_code=404, detail="Unsupported os type")

        generator = render_cisco_iosxe
        # Generera innehåll dynamiskt
        content = generator()

        # The address the device fetched from. Behind a proxy this is only the
        # device's own address if uvicorn trusts the proxy's forwarded headers
        # (FORWARDED_ALLOW_IPS). Database and broker calls are blocking, so they
        # run off the event loop.
        await run_in_threadpool(
            _start_discovery, automation_engine.jobs, request.client.host, ZtpMethod.cisco_iosxe_python
        )

        return Response(
            content=content,
            media_type="application/x-python",
            headers={"Content-Disposition": "attachment; filename=ztp.py"},
        )

    # router.add_api_route("", list_os_types, methods=["GET"], tags=tags, response_model=list[str])
    router.add_api_route("/init_config/cisco_iosxe_python/ztp.py", get_ztp_config, methods=["GET"], tags=tags)
    return router
