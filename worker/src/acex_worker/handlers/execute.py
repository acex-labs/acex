"""Operations on a node: acex.operations.execute runs raw commands, acex.operations.actions.<action>
runs an abstract action. Both log in with the node's own credentials over its management connection."""

import asyncio
import logging
from typing import Any

from acex_client import Acex
from acex_devkit.drivers import NetworkElementDriver, Session
from acex_devkit.models.actions import PingParams
from acex_devkit.models.job import JobResponse
from acex_devkit.models.operations import ActionData, CommandOutput, ExecuteData, ExecuteResult
from pydantic import BaseModel

from acex_worker.neds import load_ned

from .base_handler import Handler

log = logging.getLogger("acex_worker")


class NodeOperation(Handler):
    """Opens a session to the job's node and runs `operate` in it. Nothing is retried: a failure is the
    job's error."""

    data: type[BaseModel]

    def handle(self, client: Acex, job: JobResponse) -> BaseModel:
        data = self.data.model_validate(job.data)
        node = client.inventory.node_instances.get(data.node_id)
        driver = load_ned(client, node.asset.ned_id)
        # Client actions take keyword arguments only.
        credentials = [client.inventory.credentials.secret(id=credential.id) for credential in node.credentials]
        log.info(f"Job {job.id}: {job.type} on node {node.id}")
        return asyncio.run(self.run(driver, driver.session(node, credentials), data))

    async def run(self, driver: NetworkElementDriver, session: Session, data: Any) -> BaseModel:
        async with session:
            return await self.operate(driver, session, data)

    async def operate(self, driver: NetworkElementDriver, session: Session, data: Any) -> BaseModel:
        raise NotImplementedError


class HandleExecute(NodeOperation):
    """Runs the commands in order. Output is masked by the node's NED before it is reported, so nothing
    secret a device prints ends up in the job."""

    data = ExecuteData

    async def operate(self, driver: NetworkElementDriver, session: Session, data: ExecuteData) -> ExecuteResult:
        outputs = await session.execute(data.commands)
        return ExecuteResult(
            outputs=[
                CommandOutput(command=command, output=driver.mask(output))
                for command, output in zip(data.commands, outputs, strict=True)
            ]
        )


class HandlePing(NodeOperation):
    data = ActionData[PingParams]

    async def operate(self, driver: NetworkElementDriver, session: Session, data: ActionData) -> BaseModel:
        return await session.ping(data.params)
