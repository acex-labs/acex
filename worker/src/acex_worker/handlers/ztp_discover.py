"""acex.ztp.discover: log in to a device that fetched its ZTP bootstrap and ask what it is."""

from __future__ import annotations

import asyncio
import logging
import time

from acex_client import Acex
from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.exceptions import AuthenticationFailed, ConnectionTimeout, HostUnreachable
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.job import JobResponse
from acex_devkit.models.state import DeviceFacts
from acex_devkit.models.ztp import ZtpDiscoverData, ZtpDiscoverResult

from acex_worker.neds import load_ned

from .base_handler import Handler

log = logging.getLogger("acex_worker")


class NoNedChosen(RuntimeError):
    """No administrator has chosen a NED for the job's ZTP method."""


class NoBootstrapLogin(RuntimeError):
    """The job's ZTP method has no bootstrap login to log in to the device with."""


class HandleZtpDiscovery(Handler):
    """The job is queued when the device fetches its bootstrap, before it has applied it, so the device may not
    answer yet, or not take its login yet. It is tried again with growing pauses until `patience` seconds are
    over."""

    patience = 600
    pauses = (5, 10, 20, 30)
    #: What a device that is still applying its bootstrap does.
    not_yet = (HostUnreachable, ConnectionTimeout, AuthenticationFailed)

    sleep = staticmethod(time.sleep)
    clock = staticmethod(time.monotonic)

    def handle(self, client: Acex, job: JobResponse) -> ZtpDiscoverResult:
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

        login = CredentialSecret(
            id=0,
            credential_type="userpass",
            fields={"username": method.bootstrap_username, "password": method.bootstrap_password},
        )
        facts = self.discover(driver, str(data.ip), [login])
        if not facts.serial_number:
            raise RuntimeError(f"{data.ip} did not report a serial number")
        log.info(f"Job {job.id}: {data.ip} is {facts.serial_number}, {facts.hardware_model} {facts.os_version}")

        return ZtpDiscoverResult(
            serial_number=facts.serial_number,
            vendor=facts.vendor.value,
            hardware_model=facts.hardware_model,
            os=facts.os.value,
            os_version=facts.os_version,
        )

    def discover(self, driver: NetworkElementDriver, address: str, credentials: list[CredentialSecret]) -> DeviceFacts:
        deadline = self.clock() + self.patience
        attempt = 0
        while True:
            try:
                return asyncio.run(self.facts(driver, address, credentials))
            except self.not_yet as exc:
                pause = self.pauses[min(attempt, len(self.pauses) - 1)]
                attempt += 1
                if self.clock() + pause > deadline:
                    raise RuntimeError(
                        f"{address} did not take the bootstrap login in {self.patience} seconds: {exc}"
                    ) from exc
                log.info(f"{address} is not ready yet ({exc}); trying again in {pause} seconds")
                self.sleep(pause)

    @staticmethod
    async def facts(driver: NetworkElementDriver, address: str, credentials: list[CredentialSecret]) -> DeviceFacts:
        # No node yet: the device is only an address, so its platform is not checked.
        async with driver.connect(address, credentials) as session:
            return await session.get_facts()
