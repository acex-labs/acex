import logging

from acex.constants import BASE_URL
from acex.jobs import ZTP_DISCOVER
from acex.messaging import MessagingNotConfigured
from acex_devkit.models.ztp import ZtpMethod
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

logger = logging.getLogger("acex.api.ztp")


def render_cisco_iosxe(username: str, password: str) -> str:
    commands = [
        "hostname acex-ztp-init-device",
        "ip domain name example.com",
        # The temporary login discovery uses, until onboarding rotates it.
        f"username {username} privilege 15 secret 0 {password}",
        "crypto key generate rsa modulus 2048",
        "ip ssh version 2",
        "line vty 0 15",
        "transport input ssh",
        "login local",
        "end",
    ]
    # repr() quotes each command, so a login cannot break out of the script.
    lines = "".join(f"        {command!r},\n" for command in commands)
    return f"""#!/usr/bin/env python
import cli

print("*** ZTP: applying base configuration ***")

cli.configurep(
    [
{lines}    ]
)

cli.executep("copy running-config startup-config")
print("*** ZTP: done ***")
"""


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
        method = ZtpMethod.cisco_iosxe_python
        # Database and broker calls are blocking, so they run off the event loop.
        chosen = await run_in_threadpool(automation_engine.ztp_methods.get, method)
        if not chosen.bootstrap_username or not chosen.bootstrap_password:
            # Without a login discovery could never get in. The device retries
            # ZTP, so it comes up once an administrator has set one.
            logger.warning(f"ZTP: {request.client.host} fetched its {method} bootstrap, but no bootstrap login is set")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No bootstrap login is set for ZTP method {method}",
            )
        content = render_cisco_iosxe(chosen.bootstrap_username, chosen.bootstrap_password)

        # The address the device fetched from. Behind a proxy this is only the
        # device's own address if uvicorn trusts the proxy's forwarded headers
        # (FORWARDED_ALLOW_IPS).
        await run_in_threadpool(_start_discovery, automation_engine.jobs, request.client.host, method)

        return Response(
            content=content,
            media_type="application/x-python",
            headers={"Content-Disposition": "attachment; filename=ztp.py"},
        )

    # router.add_api_route("", list_os_types, methods=["GET"], tags=tags, response_model=list[str])
    router.add_api_route("/init_config/cisco_iosxe_python/ztp.py", get_ztp_config, methods=["GET"], tags=tags)
    return router
