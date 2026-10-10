"""acex.ztp.discover: log in to a device that fetched its ZTP bootstrap and ask what it is."""

from __future__ import annotations

import logging

from acex_client import Acex
from acex_devkit.models.job import JobResponse
from acex_devkit.models.ztp import ZtpDiscoverData, ZtpDiscoverResult

from acex_worker.neds import load_ned

from .base_handler import Handler

log = logging.getLogger("acex_worker")


class NoNedChosen(RuntimeError):
    """No administrator has chosen a NED for the job's ZTP method."""


class NoBootstrapLogin(RuntimeError):
    """The job's ZTP method has no bootstrap login to log in to the device with."""


class HandleZtpDiscovery(Handler):
    def handle(self, client: Acex, job: JobResponse) -> dict:
        data = ZtpDiscoverData.model_validate(job.data)

        # The administrator chooses the NED per method, on the ZTP settings page.
        method = client.ztp_methods.get(method=data.method)
        if method.ned is None:
            raise NoNedChosen(f"No NED is chosen for ZTP method {data.method}")
        # The temporary login the bootstrap gave the device, set per method.
        if not method.bootstrap_username or not method.bootstrap_password:
            raise NoBootstrapLogin(f"No bootstrap login is set for ZTP method {data.method}")
        driver = load_ned(client, method.ned)
        log.info(f"Job {job.id}: discovering {data.ip} ({data.method}) with NED {method.ned}")

        log.info(
            f"Logga in i {data.ip} som {method.bootstrap_username} med {type(driver).__name__} "
            "och hämta s/n, os och os_ver"
        )

        discover_data = driver.discover(data.ip, method.bootstrap_username, method.bootstrap_password)

        log.info(f"Found data: {discover_data}")

        result = ZtpDiscoverResult(
            serial_number=discover_data["serial"],
            vendor=discover_data.get("vendor"),
            hardware_model=discover_data.get("model"),
            os=discover_data.get("os"),
            os_version=discover_data.get("os_ver"),
        )
        return result.model_dump()
