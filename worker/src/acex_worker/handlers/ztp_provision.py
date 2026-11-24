"""acex.ztp.provision: push a node's full configuration to its approved device, logging in with the ZTP method's
bootstrap login."""

from __future__ import annotations

import asyncio
import logging

from acex_client import Acex
from acex_devkit.drivers import NetworkElementDriver
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.job import JobResponse
from acex_devkit.models.node_response import NodeProvisionStatus
from acex_devkit.models.ztp import ZtpProvisionData, ZtpProvisionResult

from acex_worker.neds import load_ned

from .base_handler import Handler

log = logging.getLogger("acex_worker")


class HandleZtpProvision(Handler):
    def handle(self, client: Acex, job: JobResponse) -> ZtpProvisionResult:
        job_data = ZtpProvisionData.model_validate(job.data)

        log.info(f"Job {job.id}: provisioning {job_data.node_id}")
        node = client.inventory.node_instances.get(job_data.node_id)

        driver = load_ned(client, node.asset.ned_id)

        # The device was approved at the address it was discovered at, which is the node's primary connection.
        connections = client.inventory.management_connections.query(node_id=node.id).items
        connection = next((c for c in connections if c.primary), None)
        if connection is None or not connection.target_ip:
            raise RuntimeError(f"Node {node.id} has no primary management connection with an IP")

        configuration = client.inventory.logical_nodes.configuration(id=node.logical_node_id).configuration
        method = client.ztp_methods.get(method=job_data.method)
        if not method.bootstrap_username or not method.bootstrap_password:
            raise RuntimeError(f"No bootstrap login is set for ZTP method {job_data.method}")
        login = CredentialSecret(
            id=0,
            credential_type="userpass",
            fields={"username": method.bootstrap_username, "password": method.bootstrap_password},
        )

        payload = str(driver.render(configuration, node).payload)
        lines = len([line for line in payload.splitlines() if line.strip() and line.strip() != "!"])
        output = asyncio.run(self.push(driver, node, connection.target_ip, [login], payload))

        node.provision_status = NodeProvisionStatus.provisioned
        node.save()

        return ZtpProvisionResult(lines_sent=lines, output=driver.mask(str(output or "")))

    @staticmethod
    async def push(driver: NetworkElementDriver, node, address: str, credentials: list[CredentialSecret], payload: str):
        async with driver.connect(address, credentials, node) as session:
            return await session.apply(payload)
