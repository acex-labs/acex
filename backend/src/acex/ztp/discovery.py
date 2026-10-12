"""ZTP discoveries: what a device says it is, held until an administrator approves it.

A worker's discovery only records evidence. Approving it trusts the device's
identity: the worker logged in at the source IP, so the reported serial and
facts come from the device at that address. The asset with that serial is then
created, or updated with the facts that differ (see `ApprovalPlanner`). Nodes
are never touched here; provisioning is a step of its own.
"""

import logging
from datetime import UTC, datetime

from acex.models.management_connections import ManagementConnection
from acex.models.node import Node
from acex.models.ztp_discovery import ZtpDiscovery
from acex.ztp.approval import ApprovalPlanner
from acex.ztp.review_context import ReviewContext
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import (
    IDENTITY_CONFLICTS,
    ZtpApprovalAction,
    ZtpApprovalProposal,
    ZtpBulkApproveItem,
    ZtpBulkItemResult,
    ZtpBulkOutcome,
    ZtpBulkResult,
    ZtpDiscoverData,
    ZtpDiscoverResult,
    ZtpDiscoveryResponse,
    ZtpReviewStatus,
)
from sqlmodel import func, select

logger = logging.getLogger("acex.ztp")


class ZtpDiscoveryNotFound(LookupError):
    pass


class ReviewConflict(RuntimeError):
    """The discovery cannot be approved or rejected; `proposal` is what approval would have done, if known."""

    def __init__(self, message: str, proposal: ZtpApprovalProposal | None = None):
        super().__init__(message)
        self.proposal = proposal


class ProposalChanged(ReviewConflict):
    """What approval would do is no longer what the administrator saw."""


def record_discovery(session, job, result: ZtpDiscoverResult) -> None:
    """Store a finished discovery job's result. The job type's success hook, run in the job's transaction."""
    data = ZtpDiscoverData.model_validate(job.data)
    discovery = ZtpDiscovery(job_id=job.id, source_ip=str(data.ip), **result.model_dump())
    session.add(discovery)
    session.flush()
    logger.info(f"ZTP: {discovery.source_ip} says it is {result.serial_number}; discovery {discovery.id} awaits review")


class ZtpDiscoveryManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def list_discoveries(
        self,
        *,
        review_status: ZtpReviewStatus | None = None,
        asset_id: int | None = None,
        serial_number: str | None = None,
        source_ip: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[ZtpDiscoveryResponse]:
        """Discoveries, newest first, each with its conflicts and what approving it would do."""
        given = {
            ZtpDiscovery.review_status: review_status,
            ZtpDiscovery.asset_id: asset_id,
            ZtpDiscovery.serial_number: serial_number,
            ZtpDiscovery.source_ip: source_ip,
        }
        filters = [column == value for column, value in given.items() if value is not None]
        with self._session() as session:
            total = session.exec(select(func.count()).select_from(ZtpDiscovery).where(*filters)).one()
            rows = session.exec(
                select(ZtpDiscovery)
                .where(*filters)
                .order_by(ZtpDiscovery.created_at.desc(), ZtpDiscovery.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            items = self._responses(session, list(rows))
        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    def get(self, discovery_id: int) -> ZtpDiscoveryResponse:
        with self._session() as session:
            return self._responses(session, [self._discovery(session, discovery_id)])[0]

    def approve(self, discovery_id: int, *, reviewed_by: str, proposal_hash: str | None = None) -> ZtpDiscoveryResponse:
        """Trust the discovery: the asset with its serial is created or updated as proposed."""
        with self._session() as session:
            discovery, _ = self._approve(session, discovery_id, reviewed_by, proposal_hash, bulk=False)
            session.commit()
            return self._responses(session, [discovery])[0]

    def reject(self, discovery_id: int, *, reviewed_by: str) -> ZtpDiscoveryResponse:
        """Distrust the discovery. Nothing else changes."""
        with self._session() as session:
            discovery = self._reject(session, discovery_id, reviewed_by)
            session.commit()
            return self._responses(session, [discovery])[0]

    def approve_many(
        self, items: list[ZtpBulkApproveItem], *, reviewed_by: str, dry_run: bool = False
    ) -> ZtpBulkResult:
        """Approve each discovery that can be, skipping the rest with a reason.

        A discovery with an identity conflict is skipped: it has to be approved
        on its own. A dry run goes through exactly the same steps and then
        rolls back, so it reports what a real run would do.
        """
        outcome = ZtpBulkOutcome.would_approve if dry_run else ZtpBulkOutcome.approved
        results = []
        with self._session() as session:
            for item in items:
                try:
                    _, proposal = self._approve(session, item.discovery_id, reviewed_by, item.proposal_hash, bulk=True)
                    results.append(
                        ZtpBulkItemResult(discovery_id=item.discovery_id, outcome=outcome, proposal=proposal)
                    )
                except (ReviewConflict, ZtpDiscoveryNotFound) as exc:
                    results.append(self._skipped(item.discovery_id, exc))
            if dry_run:
                session.rollback()
            else:
                session.commit()
                approved = sum(r.outcome == outcome for r in results)
                logger.info(f"ZTP: {reviewed_by} approved {approved} of {len(items)} discoveries")
        return self._bulk_result(results)

    def reject_many(self, discovery_ids: list[int], *, reviewed_by: str) -> ZtpBulkResult:
        results = []
        with self._session() as session:
            for discovery_id in discovery_ids:
                try:
                    self._reject(session, discovery_id, reviewed_by)
                    results.append(ZtpBulkItemResult(discovery_id=discovery_id, outcome=ZtpBulkOutcome.rejected))
                except (ReviewConflict, ZtpDiscoveryNotFound) as exc:
                    results.append(self._skipped(discovery_id, exc))
            session.commit()
        return self._bulk_result(results)

    def _session(self):
        """A session for one operation, closed when the `with` block ends."""
        return next(self.db.get_session())

    def _approve(self, session, discovery_id: int, reviewed_by: str, proposal_hash: str | None, *, bulk: bool):
        """Check, then apply, one approval. Raises before writing anything if it cannot be done."""
        discovery = self._unreviewed(session, discovery_id)
        ctx = ReviewContext.load(session, [discovery])
        planner = ApprovalPlanner(ctx)
        proposal = planner.plan(discovery)

        if proposal_hash is not None and proposal_hash != proposal.hash:
            raise ProposalChanged(
                f"What approving discovery {discovery.id} would do has changed; review it again.", proposal
            )
        if proposal.action == ZtpApprovalAction.blocked:
            raise ReviewConflict("; ".join(proposal.blocked_by), proposal)
        identity = [c for c in ctx.conflicts(discovery) if c.kind in IDENTITY_CONFLICTS]
        if bulk and identity:
            raise ReviewConflict(f"{identity[0].message}; approve it on its own", proposal)

        asset = planner.apply(session, proposal)
        discovery.asset_id = asset.id
        now = datetime.now(UTC)
        self._review(session, discovery, ZtpReviewStatus.approved, reviewed_by, now)
        # Only one report can be the device that serial belongs to.
        others = session.exec(
            select(ZtpDiscovery).where(
                ZtpDiscovery.serial_number == discovery.serial_number,
                ZtpDiscovery.id != discovery.id,
                ZtpDiscovery.review_status == ZtpReviewStatus.unreviewed,
            )
        ).all()
        for other in others:
            self._review(session, other, ZtpReviewStatus.rejected, reviewed_by, now)
        node = ctx.node_of(discovery)
        if node is not None:
            self.learn_connection(session, node, discovery.source_ip)
        session.flush()
        logger.info(
            f"ZTP: {reviewed_by} approved discovery {discovery.id} from {discovery.source_ip}: "
            f"{proposal.action} asset {asset.id} ({discovery.serial_number})"
        )
        return discovery, proposal

    @staticmethod
    def learn_connection(session, node: Node, ip: str) -> None:
        """Give the node a management connection to the IP its approved device was reached at.

        Kept alongside the node's other connections; it is primary only if the node has none.
        """
        connections = session.exec(select(ManagementConnection).where(ManagementConnection.node_id == node.id)).all()
        if any(c.target_ip == ip for c in connections):
            return
        primary = not any(c.primary for c in connections)
        session.add(ManagementConnection(node_id=node.id, target_ip=ip, primary=primary))
        logger.info(f"ZTP: node {node.id} gets management connection {ip} (primary={primary}) from its discovery")

    def _reject(self, session, discovery_id: int, reviewed_by: str) -> ZtpDiscovery:
        discovery = self._unreviewed(session, discovery_id)
        self._review(session, discovery, ZtpReviewStatus.rejected, reviewed_by, datetime.now(UTC))
        session.flush()
        logger.info(f"ZTP: {reviewed_by} rejected discovery {discovery.id} from {discovery.source_ip}")
        return discovery

    def _discovery(self, session, discovery_id: int) -> ZtpDiscovery:
        discovery = session.get(ZtpDiscovery, discovery_id)
        if discovery is None:
            raise ZtpDiscoveryNotFound(f"No discovery {discovery_id}.")
        return discovery

    def _unreviewed(self, session, discovery_id: int) -> ZtpDiscovery:
        discovery = self._discovery(session, discovery_id)
        if discovery.review_status != ZtpReviewStatus.unreviewed:
            raise ReviewConflict(f"Discovery {discovery.id} is already {discovery.review_status}.")
        return discovery

    @staticmethod
    def _review(session, discovery: ZtpDiscovery, status: ZtpReviewStatus, reviewed_by: str, at: datetime) -> None:
        discovery.review_status = status
        discovery.reviewed_by = reviewed_by
        discovery.reviewed_at = at
        session.add(discovery)

    @staticmethod
    def _responses(session, discoveries: list[ZtpDiscovery]) -> list[ZtpDiscoveryResponse]:
        ctx = ReviewContext.load(session, discoveries)
        planner = ApprovalPlanner(ctx)
        responses = []
        for discovery in discoveries:
            response = ZtpDiscoveryResponse.model_validate(discovery)
            node = ctx.node_of(discovery)
            if node is not None:
                response.node_id, response.node_hostname = node.id, ctx.hostname_of(node)
            response.conflicts = ctx.conflicts(discovery)
            if discovery.review_status == ZtpReviewStatus.unreviewed:
                response.proposal = planner.plan(discovery)
            responses.append(response)
        return responses

    @staticmethod
    def _skipped(discovery_id: int, exc: ReviewConflict | ZtpDiscoveryNotFound) -> ZtpBulkItemResult:
        proposal = exc.proposal if isinstance(exc, ReviewConflict) else None
        return ZtpBulkItemResult(
            discovery_id=discovery_id, outcome=ZtpBulkOutcome.skipped, reason=str(exc), proposal=proposal
        )

    @staticmethod
    def _bulk_result(results: list[ZtpBulkItemResult]) -> ZtpBulkResult:
        """Counts per outcome, and per proposal action for the discoveries that were (or would be) approved."""
        summary: dict[str, int] = {}
        for result in results:
            summary[result.outcome] = summary.get(result.outcome, 0) + 1
            if result.outcome != ZtpBulkOutcome.skipped and result.proposal is not None:
                summary[result.proposal.action] = summary.get(result.proposal.action, 0) + 1
        return ZtpBulkResult(results=results, summary=summary)
