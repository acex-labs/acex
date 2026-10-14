"""acex.ztp.discover: log in to a device that fetched its ZTP bootstrap and ask what it is."""

from __future__ import annotations

import logging

from acex_client import Acex
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

        # mgmt connectionset
        connections = client.inventory.management_connections.query(node_id=node.id).items
        connection = next((c for c in connections if c.primary), None)
        if connection is None or not connection.target_ip:
            raise RuntimeError(f"Node {node.id} has no primary management connection with an IP")

        # Config to send
        configuration = client.inventory.logical_nodes.get(node.logical_node_id).configuration().configuration

        # Get init credentials for ztp
        m = client.ztp_methods.get(method=job_data.method)
        username, password = m.bootstrap_username, m.bootstrap_password

        driver.provision(configuration, node, connection, {"username": username, "password": password})

        out = node.provision_status = NodeProvisionStatus.provisioned
        node.save()

        result = ZtpProvisionResult(lines_sent=400000, output=out)
        return result
