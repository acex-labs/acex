"""Each node's place in ZTP, worked out from everything it depends on, loaded in a few queries."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial

from acex.models.asset import Asset
from acex.models.job import Job, JobState
from acex.models.logical_node import LogicalNode
from acex.models.node import AssetRefType, Node, NodeProvisionStatus
from acex.models.ztp_discovery import ZtpDiscovery
from acex.settings import ZtpSettings
from acex_devkit.models.job import JobSubjectType
from acex_devkit.models.ztp import ZtpAssetReadiness, ZtpNodeAsset, ZtpPipelineNode, ZtpReviewStatus, ZtpStage
from sqlmodel import select

#: The provisioning job type, registered in acex.jobs.types.
ZTP_PROVISION = "acex.ztp.provision"

#: Job states in which a provisioning job is still on its way.
ACTIVE_JOB_STATES = (JobState.queued, JobState.running)

_READINESS_STAGE = {
    None: ZtpStage.awaiting_device,
    ZtpAssetReadiness.unseen: ZtpStage.awaiting_device,
    ZtpAssetReadiness.awaiting_review: ZtpStage.awaiting_approval,
    ZtpAssetReadiness.ready: ZtpStage.ready,
}


@dataclass
class PipelineView:
    settings: ZtpSettings
    logical: dict[int, LogicalNode] = field(default_factory=dict)
    assets: dict[int, Asset] = field(default_factory=dict)
    #: Discoveries of each serial, newest first.
    sightings: dict[str, list[ZtpDiscovery]] = field(default_factory=dict)
    #: The newest provisioning job of each provisioning node.
    latest_jobs: dict[int, Job] = field(default_factory=dict)
    now: datetime = field(default_factory=partial(datetime.now, UTC))

    @classmethod
    def load(cls, session, nodes: list[Node], settings: ZtpSettings) -> "PipelineView":
        view = cls(settings)
        logical_ids = {n.logical_node_id for n in nodes}
        view.logical = {ln.id: ln for ln in session.exec(select(LogicalNode).where(LogicalNode.id.in_(logical_ids)))}

        asset_ids = {n.asset_ref_id for n in nodes if n.asset_ref_type == AssetRefType.asset}
        view.assets = {a.id: a for a in session.exec(select(Asset).where(Asset.id.in_(asset_ids)))}

        serials = {a.serial_number for a in view.assets.values()}
        for d in session.exec(
            select(ZtpDiscovery)
            .where(ZtpDiscovery.serial_number.in_(serials))
            .order_by(ZtpDiscovery.created_at.desc(), ZtpDiscovery.id.desc())
        ):
            view.sightings.setdefault(d.serial_number, []).append(d)

        provisioning = {n.id for n in nodes if n.provision_status == NodeProvisionStatus.provisioning}
        for job in session.exec(
            select(Job)
            .where(Job.type == ZTP_PROVISION, Job.subject_type == JobSubjectType.node, Job.subject_id.in_(provisioning))
            .order_by(Job.created_at.desc(), Job.id.desc())
        ):
            view.latest_jobs.setdefault(job.subject_id, job)
        return view

    def row(self, node: Node) -> ZtpPipelineNode:
        ln = self.logical.get(node.logical_node_id)
        asset = self.assets.get(node.asset_ref_id) if node.asset_ref_type == AssetRefType.asset else None
        discoveries = self.sightings.get(asset.serial_number, []) if asset is not None else []
        readiness = self._readiness(asset, discoveries)
        approved = next(
            (d for d in discoveries if d.review_status == ZtpReviewStatus.approved and d.asset_id == asset.id), None
        )
        if node.provision_status == NodeProvisionStatus.enrolled:
            stage = _READINESS_STAGE[readiness]
        else:
            stage = ZtpStage(str(node.provision_status))
        return ZtpPipelineNode(
            node_id=node.id,
            hostname=ln.hostname if ln else None,
            site=ln.site if ln else None,
            admin_status=str(node.admin_status),
            provision_status=str(node.provision_status),
            ztp_previous_status=self._text(node.ztp_previous_status),
            stage=stage,
            stalled=self._stalled(node),
            asset=self._asset(asset),
            readiness=readiness,
            last_seen=discoveries[0].created_at if discoveries else None,
            approved_ip=approved.source_ip if approved else None,
        )

    def _stalled(self, node: Node) -> str | None:
        """Why a provisioning node is not getting anywhere, or None if its job is on its way."""
        if node.provision_status != NodeProvisionStatus.provisioning:
            return None
        job = self.latest_jobs.get(node.id)
        if job is None:
            return "No provisioning job"
        if job.state not in ACTIVE_JOB_STATES:
            return f"Job #{job.id} is {job.state}"
        if job.state == JobState.queued:
            waited = self.now - self._utc(job.created_at)
            if waited > timedelta(minutes=self.settings.provision_queue_timeout_minutes):
                return f"Job #{job.id} not picked up by a worker for {self._minutes(waited)} min"
            return None
        running = self.now - self._utc(job.started_at or job.created_at)
        if running > timedelta(minutes=self.settings.provision_run_timeout_minutes):
            return f"Job #{job.id} has run for {self._minutes(running)} min without finishing"
        return None

    @staticmethod
    def _readiness(asset: Asset | None, discoveries: list[ZtpDiscovery]) -> ZtpAssetReadiness | None:
        if asset is None:
            return None
        latest = next((d for d in discoveries if d.review_status != ZtpReviewStatus.rejected), None)
        if latest is None:
            return ZtpAssetReadiness.unseen
        if latest.review_status == ZtpReviewStatus.unreviewed:
            return ZtpAssetReadiness.awaiting_review
        return ZtpAssetReadiness.ready

    @classmethod
    def _asset(cls, asset: Asset | None) -> ZtpNodeAsset | None:
        if asset is None:
            return None
        return ZtpNodeAsset(
            id=asset.id,
            serial_number=asset.serial_number,
            vendor=cls._text(asset.vendor),
            hardware_model=asset.hardware_model,
            os=cls._text(asset.os),
            os_version=asset.os_version,
            ned_id=asset.ned_id,
        )

    @staticmethod
    def _text(value) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        # SQLite hands datetimes back without their zone; they are stored in UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    @staticmethod
    def _minutes(delta: timedelta) -> int:
        return int(delta.total_seconds() // 60)
