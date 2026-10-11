"""Where each node stands in ZTP, and taking a node into or out of it.

A node is in ZTP while it is enrolled, provisioning or failed. An enrolled
node's stage comes from its asset: whether the device with that serial has been
discovered, and whether an administrator has trusted its identity. From then on
it is the node's provision_status.

ZTP can always be cancelled: the node returns to the status it had when it was
enrolled. Only a device that a worker may have started configuring is left
failed instead, since nothing can be said about its configuration.
"""

import logging
from datetime import UTC, datetime

from acex.models.job import Job, JobState
from acex.models.node import AssetRefType, Node, NodeProvisionStatus
from acex.models.ztp_discovery import ZtpDiscovery
from acex.settings import ZtpSettings
from acex.ztp.pipeline_view import ACTIVE_JOB_STATES, ZTP_PROVISION, PipelineView
from acex_devkit.models.job import JobResponse, JobSubjectType
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import (
    PIPELINE_STAGES,
    ZtpNodeDetail,
    ZtpPipelineNode,
    ZtpPipelineSummary,
    ZtpReviewStatus,
    ZtpStage,
)
from sqlalchemy import update
from sqlmodel import func, select

logger = logging.getLogger("acex.ztp")

#: The statuses of a node in ZTP.
_IN_ZTP = (NodeProvisionStatus.enrolled, NodeProvisionStatus.provisioning, NodeProvisionStatus.failed)

#: The statuses a node can be enrolled from.
_ENROLLABLE = (NodeProvisionStatus.unprovisioned, NodeProvisionStatus.adopted, NodeProvisionStatus.provisioned)

#: What needs a human first, then furthest along.
_ORDER = [ZtpStage.failed, ZtpStage.awaiting_approval, ZtpStage.ready, ZtpStage.provisioning, ZtpStage.awaiting_device]


class ZtpNodeNotFound(LookupError):
    pass


class ZtpNodeConflict(RuntimeError):
    """The node is not in a state where the action can be taken."""


class ZtpPipelineManager:
    def __init__(self, db_manager, discoveries, settings: ZtpSettings | None = None):
        self.db = db_manager
        self.discoveries = discoveries
        self.settings = settings or ZtpSettings()

    def list_nodes(
        self, *, stage: ZtpStage | None = None, stalled: bool | None = None, limit: int = 100, offset: int = 0
    ) -> PaginatedResponse[ZtpPipelineNode]:
        """Nodes in the pipeline, what needs a human first."""
        wanted = {stage} if stage is not None else set(PIPELINE_STAGES)
        query = select(Node)
        if wanted <= set(PIPELINE_STAGES):
            query = query.where(Node.provision_status.in_(_IN_ZTP))
        with self._session() as session:
            rows = self._rows(session, session.exec(query).all())
        rows = [r for r in rows if r.stage in wanted and (stalled is None or bool(r.stalled) == stalled)]
        rows.sort(key=self._priority)
        return PaginatedResponse(items=rows[offset : offset + limit], total=len(rows), limit=limit, offset=offset)

    def summary(self) -> ZtpPipelineSummary:
        with self._session() as session:
            rows = self._rows(session, session.exec(select(Node)).all())
            bound = select(Node.asset_ref_id).where(Node.asset_ref_type == AssetRefType.asset)
            pool = session.exec(
                select(func.count(func.distinct(ZtpDiscovery.asset_id))).where(
                    ZtpDiscovery.review_status == ZtpReviewStatus.approved,
                    ZtpDiscovery.asset_id.is_not(None),
                    ZtpDiscovery.asset_id.not_in(bound),
                )
            ).one()
        stages = {s: 0 for s in ZtpStage}
        for row in rows:
            stages[row.stage] += 1
        return ZtpPipelineSummary(stages=stages, pool=pool, stalled=sum(1 for r in rows if r.stalled))

    def get(self, node_id: int) -> ZtpNodeDetail:
        with self._session() as session:
            [row] = self._rows(session, [self._node(session, node_id)])
            jobs = session.exec(
                select(Job)
                .where(Job.type == ZTP_PROVISION, Job.subject_type == JobSubjectType.node, Job.subject_id == node_id)
                .order_by(Job.created_at.desc(), Job.id.desc())
                .limit(20)
            ).all()
            provision_jobs = [JobResponse.model_validate(job, from_attributes=True) for job in jobs]
        discoveries = (
            self.discoveries.list_discoveries(serial_number=row.asset.serial_number, limit=50).items
            if row.asset is not None
            else []
        )
        return ZtpNodeDetail(**row.model_dump(), discoveries=discoveries, provision_jobs=provision_jobs)

    def enroll(self, node_id: int, *, by: str) -> ZtpNodeDetail:
        """Take the node into ZTP. Its stage then follows its asset until provisioning starts."""
        with self._session() as session:
            node = self._node(session, node_id, lock=True)
            if node.asset_ref_type != AssetRefType.asset:
                raise ZtpNodeConflict(f"Node {node.id} is bound to an asset cluster; ZTP handles single assets only.")
            if node.provision_status not in _ENROLLABLE:
                raise ZtpNodeConflict(f"Node {node.id} is {node.provision_status}; it is already in ZTP.")
            node.ztp_previous_status = node.provision_status
            self._set_status(session, node, NodeProvisionStatus.enrolled)
            session.commit()
            logger.info(f"ZTP: {by} enrolled node {node.id} (was {node.ztp_previous_status})")
        return self.get(node_id)

    def cancel(self, node_id: int, *, by: str) -> ZtpNodeDetail:
        """Take the node out of ZTP, back to the status it had when it was enrolled.

        A node whose provisioning job was running is left failed instead: the
        worker may have started configuring the device. Cancelling again then
        takes it out.
        """
        with self._session() as session:
            node = self._node(session, node_id, lock=True)
            if node.provision_status not in _IN_ZTP:
                raise ZtpNodeConflict(f"Node {node.id} is {node.provision_status}; it is not in ZTP.")
            if self._cancel_jobs(session, node, by):
                self._set_status(session, node, NodeProvisionStatus.failed)
                outcome = "failed: its device may be partly configured"
            else:
                previous = node.ztp_previous_status or NodeProvisionStatus.unprovisioned
                node.ztp_previous_status = None
                self._set_status(session, node, previous)
                outcome = f"back to {previous}"
            session.commit()
            logger.info(f"ZTP: {by} cancelled ZTP of node {node.id}; {outcome}")
        return self.get(node_id)

    def reset(self, node_id: int, *, by: str) -> ZtpNodeDetail:
        """Step back from provisioning or failed to enrolled; the stage follows the asset again (usually ready)."""
        with self._session() as session:
            node = self._node(session, node_id, lock=True)
            if node.provision_status not in (NodeProvisionStatus.provisioning, NodeProvisionStatus.failed):
                raise ZtpNodeConflict(
                    f"Node {node.id} is {node.provision_status}; only provisioning or failed can step back."
                )
            self._cancel_jobs(session, node, by)
            self._set_status(session, node, NodeProvisionStatus.enrolled)
            session.commit()
            logger.info(f"ZTP: {by} stepped node {node.id} back from provisioning")
        return self.get(node_id)

    def _session(self):
        """A session for one operation, closed when the `with` block ends."""
        return next(self.db.get_session())

    @staticmethod
    def _priority(row: ZtpPipelineNode) -> tuple:
        """Stalled first, then what needs a human, then furthest along."""
        stage = _ORDER.index(row.stage) if row.stage in _ORDER else len(_ORDER)
        return (not row.stalled, stage, row.hostname or "")

    def _rows(self, session, nodes) -> list[ZtpPipelineNode]:
        nodes = list(nodes)
        view = PipelineView.load(session, nodes, self.settings)
        return [view.row(node) for node in nodes]

    @staticmethod
    def _node(session, node_id: int, *, lock: bool = False) -> Node:
        query = select(Node).where(Node.id == node_id)
        if lock:
            # Two administrators acting on the node at once take turns.
            query = query.with_for_update()
        node = session.exec(query).first()
        if node is None:
            raise ZtpNodeNotFound(f"No node {node_id}.")
        return node

    @staticmethod
    def _set_status(session, node: Node, status: NodeProvisionStatus) -> None:
        node.provision_status = status
        node.updated_at = datetime.now(UTC)
        session.add(node)

    @staticmethod
    def _cancel_jobs(session, node: Node, by: str) -> bool:
        """Cancel the node's queued or running provisioning jobs; True if one was running.

        A worker still running a cancelled job gets 409 when it reports, so it
        cannot move the node afterwards.
        """
        active = session.exec(
            select(Job).where(
                Job.type == ZTP_PROVISION,
                Job.subject_type == JobSubjectType.node,
                Job.subject_id == node.id,
                Job.state.in_(ACTIVE_JOB_STATES),
            )
        ).all()
        if not active:
            return False
        # Read before the update, which brings the loaded jobs up to date.
        was_running = any(job.state == JobState.running for job in active)
        session.execute(
            update(Job)
            .where(Job.id.in_([job.id for job in active]), Job.state.in_(ACTIVE_JOB_STATES))
            .values(state=JobState.cancelled, cancelled_by=by, finished_at=datetime.now(UTC))
        )
        return was_running
