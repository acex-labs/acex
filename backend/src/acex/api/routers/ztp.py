import logging

from acex.constants import BASE_URL
from acex.jobs import ZTP_DISCOVER
from acex.messaging import MessagingNotConfigured
from acex.ztp.bootstrap import BOOTSTRAPS
from acex_devkit.models.ztp import ZtpMethod
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

logger = logging.getLogger("acex.api.ztp")


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


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/ztp")
    tags = ["Ztp"]

    async def get_ztp_config(method: str, filename: str, request: Request):
        bootstrap = BOOTSTRAPS.get(method)
        if bootstrap is None or bootstrap.filename != filename:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        method = bootstrap.method
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
        content = bootstrap.render(chosen.bootstrap_username, chosen.bootstrap_password)

        # The address the device fetched from. Behind a proxy this is only the
        # device's own address if uvicorn trusts the proxy's forwarded headers
        # (FORWARDED_ALLOW_IPS).
        await run_in_threadpool(_start_discovery, automation_engine.jobs, request.client.host, method)

        return Response(
            content=content,
            media_type=bootstrap.media_type,
            headers={"Content-Disposition": f"attachment; filename={bootstrap.filename}"},
        )

    router.add_api_route("/init_config/{method}/{filename}", get_ztp_config, methods=["GET"], tags=tags)
    return router
