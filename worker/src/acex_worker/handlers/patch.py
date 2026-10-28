"""acex.operations.patch.render renders the patch a node's configuration needs at a path; acex.operations.patch.apply
sends it. Both read the node live and diff that against its desired configuration, and upload each read as the
node's observed configuration."""

import asyncio
import hashlib
import logging
from typing import Any

from acex_client import Acex
from acex_client.exceptions import AcexHTTPError
from acex_devkit.configdiffer import ConfigDiffer, Diff
from acex_devkit.drivers import NetworkElementDriver, Session
from acex_devkit.models.config_snapshot import DeviceConfigUpload
from acex_devkit.models.operations import (
    PatchApplyData,
    PatchApplyResult,
    PatchChange,
    PatchOutcome,
    PatchRenderData,
    PatchRenderResult,
    PatchScope,
)
from pydantic import BaseModel

from .execute import NodeOperation

log = logging.getLogger("acex_worker")


class PatchOperation(NodeOperation):
    """Holds the node and its desired configuration while a session to it is open."""

    def on_node(self, client: Acex, node_id: int, data: Any) -> BaseModel:
        self.client = client
        self.node = client.inventory.node_instances.get(node_id)
        self.desired = client.inventory.logical_nodes.configuration(id=self.node.logical_node_id).configuration
        return self.in_session(client, self.node, data)

    async def read(self, driver: NetworkElementDriver, session: Session, scope: PatchScope) -> Diff:
        """What differs within the scope, read live. The read is masked before it is parsed, as an uploaded
        one is, so a secret the device shows hashed matches the desired one."""
        raw = await session.get_config()
        await asyncio.to_thread(self.upload, raw)
        observed = driver.parse(driver.mask(driver.normalize(raw)), self.node).configuration
        diff = ConfigDiffer().diff(desired_config=self.desired, observed_config=observed)
        return diff.scoped(scope.path, scope.prune)

    def render(self, driver: NetworkElementDriver, diff: Diff) -> str:
        if diff.is_empty():
            return ""
        patch = driver.render_patch(diff, self.node)
        if not patch.strip():
            paths = ", ".join(".".join(change.path) for change in diff.get_all_changes())
            raise RuntimeError(f"{type(driver).__name__} renders nothing for {paths}")
        return patch

    def upload(self, raw: str) -> None:
        """Keep the read as the node's observed configuration. Never fails the job."""
        try:
            self.client.inventory.node_instances.upload_observed(self.node.id, payload=DeviceConfigUpload(content=raw))
        except AcexHTTPError as exc:
            if exc.status_code != 409:  # 409: unchanged since the last one
                log.warning(f"Node {self.node.id}: uploading the configuration read failed: {exc}")

    @staticmethod
    def digest(patch: str) -> str:
        return hashlib.sha256(patch.encode()).hexdigest()

    @staticmethod
    def changes(diff: Diff) -> list[PatchChange]:
        return [
            PatchChange(
                op=change.op,
                path=".".join(change.path),
                attributes=[attribute.attribute_name for attribute in change.changed_attributes],
            )
            for change in diff.get_all_changes()
        ]


class HandlePatchRender(PatchOperation):
    """Renders the patch and reports it masked, with a hash of it unmasked for an apply to check against."""

    data = PatchRenderData

    async def operate(self, driver: NetworkElementDriver, session: Session, data: PatchRenderData) -> BaseModel:
        diff = await self.read(driver, session, data)
        patch = self.render(driver, diff)
        return PatchRenderResult(
            patch=driver.mask(patch),
            patch_hash=self.digest(patch) if patch else None,
            changes=self.changes(diff),
        )


class HandlePatchApply(PatchOperation):
    """Renders the patch again and sends it only if it is the one planned, then reads the node once more to
    see that nothing differs within the scope any more."""

    data = PatchApplyData

    async def operate(self, driver: NetworkElementDriver, session: Session, data: PatchApplyData) -> BaseModel:
        diff = await self.read(driver, session, data)
        patch = self.render(driver, diff)
        if self.digest(patch) != data.patch_hash:
            log.info(f"Node {data.node_id}: not patched, it renders another patch than plan {data.plan_id}")
            return PatchApplyResult(outcome=PatchOutcome.changed, changes=self.changes(diff))
        output = await session.apply(patch)
        residual = await self.read(driver, session, data)
        return PatchApplyResult(
            outcome=PatchOutcome.residual if not residual.is_empty() else PatchOutcome.applied,
            patch=driver.mask(patch),
            output=driver.mask(str(output or "")),
            changes=self.changes(residual),
        )
