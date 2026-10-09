"""acex.ztp.discover: log in to a device that fetched its ZTP bootstrap and ask what it is."""

from __future__ import annotations

import logging

from acex_client import Acex
from acex_devkit.models.job import JobResponse

from .base_handler import Handler

log = logging.getLogger("acex_worker")


class HandleZtpDiscovery(Handler):
    def handle(self, client: Acex, job: JobResponse) -> dict:
        log.info("Nu ska vi logga in i switchen!")
        log.info("Logga in i swirren och hämta s/n, os och os_ver")
        log.info("Kolla i acex om serienummer finns på asset")
        log.info("Skapa asset om S/n inte finns")
        log.info("Mappa mot befintlig asset om s/n finns sedan innan")
