"""ZTP discoveries: what a device says it is, held until an administrator approves it.

A worker's discovery only records evidence. It is matched to the node whose
claimed asset has the reported serial number, which then waits in
awaiting_approval; nothing about the device is trusted until an administrator
approves it.
"""

import logging
from datetime import UTC, datetime

from acex.models.asset import Asset
from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.node import AssetRefType, Node, NodeProvisionStatus
from acex.models.ztp_discovery import ZtpDiscovery
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.ztp import (
    ZtpConflict,
    ZtpConflictKind,
    ZtpDiscoverData,
    ZtpDiscoverResult,
    ZtpDiscoveryResponse,
    ZtpExpected,
    ZtpReviewStatus,
)
from sqlmodel import func, select

logger = logging.getLogger("acex.ztp")

_FACTS = ("vendor", "hardware_model", "os", "os_version")


class ZtpDiscoveryNotFound(LookupError):
    pass


class ReviewConflict(RuntimeError):
    """The discovery or its node is not in a state where it can be approved or rejected."""


def record_discovery(session, job, result: ZtpDiscoverResult) -> None:
    """Store a finished discovery job's result and match it to a node awaiting its device.

    Runs in the transaction that marks the job succeeded.
    """
    data = ZtpDiscoverData.model_validate(job.data)
    discovery = ZtpDiscovery(job_id=job.id, source_ip=str(data.ip), **result.model_dump())

    # A device that was rediscovered before anyone reviewed it still matches
    # its node, so the administrator sees both reports side by side.
    node = session.exec(
        select(Node)
        .join(Asset, Asset.id == Node.asset_ref_id)
        .where(
            Node.asset_ref_type == AssetRefType.asset,
            Asset.serial_number == result.serial_number,
            Node.provision_status.in_([NodeProvisionStatus.awaiting_device, NodeProvisionStatus.awaiting_approval]),
        )
    ).first()
    if node is not None:
        discovery.node_id = node.id
        node.provision_status = NodeProvisionStatus.awaiting_approval
        node.updated_at = datetime.now(UTC)
        session.add(node)
    session.add(discovery)
    session.flush()

    if node is not None:
        logger.info(f"ZTP: {discovery.source_ip} says it is {result.serial_number}; node {node.id} awaits approval")
    else:
        logger.info(f"ZTP: {discovery.source_ip} says it is {result.serial_number}; no claimed node matches")


class ZtpDiscoveryManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def list_discoveries(
        self,
        *,
        review_status: ZtpReviewStatus | None = None,
        node_id: int | None = None,
        serial_number: str | None = None,
        source_ip: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[ZtpDiscoveryResponse]:
        """Discoveries, newest first, each with what it is expected to be and its conflicts."""
        filters = []
        if review_status is not None:
            filters.append(ZtpDiscovery.review_status == review_status)
        if node_id is not None:
            filters.append(ZtpDiscovery.node_id == node_id)
        if serial_number is not None:
            filters.append(ZtpDiscovery.serial_number == serial_number)
        if source_ip is not None:
            filters.append(ZtpDiscovery.source_ip == source_ip)

        session = next(self.db.get_session())
        try:
            total = session.exec(select(func.count()).select_from(ZtpDiscovery).where(*filters)).one()
            rows = session.exec(
                select(ZtpDiscovery)
                .where(*filters)
                .order_by(ZtpDiscovery.created_at.desc(), ZtpDiscovery.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            items = [self._response(session, row) for row in rows]
            return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
        finally:
            session.close()

    def get(self, discovery_id: int) -> ZtpDiscoveryResponse:
        session = next(self.db.get_session())
        try:
            return self._response(session, self._discovery(session, discovery_id))
        finally:
            session.close()

    def approve(self, discovery_id: int, *, reviewed_by: str) -> ZtpDiscoveryResponse:
        """Trust the discovery: its node is provisioned at the IP the device reported from.

        Any other unreviewed discovery of the same node is rejected, since only
        one device can be the node.
        """
        session = next(self.db.get_session())
        try:
            discovery = self._unreviewed(session, discovery_id)
            if discovery.node_id is None:
                raise ReviewConflict(f"Discovery {discovery.id} matched no node; claim its asset first.")
            node = session.get(Node, discovery.node_id)
            if node is None or node.provision_status != NodeProvisionStatus.awaiting_approval:
                status = node.provision_status if node is not None else "gone"
                raise ReviewConflict(f"Node {discovery.node_id} is {status}, not awaiting approval.")

            now = datetime.now(UTC)
            self._review(session, discovery, ZtpReviewStatus.approved, reviewed_by, now)
            others = session.exec(
                select(ZtpDiscovery).where(
                    ZtpDiscovery.node_id == node.id,
                    ZtpDiscovery.id != discovery.id,
                    ZtpDiscovery.review_status == ZtpReviewStatus.unreviewed,
                )
            ).all()
            for other in others:
                self._review(session, other, ZtpReviewStatus.rejected, reviewed_by, now)

            self._set_management_ip(session, node.id, discovery.source_ip)
            node.provision_status = NodeProvisionStatus.provisioning
            node.updated_at = now
            session.add(node)
            session.commit()
            logger.info(
                f"ZTP: {reviewed_by} approved discovery {discovery.id}; node {node.id} at {discovery.source_ip}"
            )
            return self._response(session, discovery)
        finally:
            session.close()

    def reject(self, discovery_id: int, *, reviewed_by: str) -> ZtpDiscoveryResponse:
        """Distrust the discovery. Its node waits for the right device again, unless another report awaits review."""
        session = next(self.db.get_session())
        try:
            discovery = self._unreviewed(session, discovery_id)
            now = datetime.now(UTC)
            self._review(session, discovery, ZtpReviewStatus.rejected, reviewed_by, now)

            node = session.get(Node, discovery.node_id) if discovery.node_id is not None else None
            if node is not None and node.provision_status == NodeProvisionStatus.awaiting_approval:
                pending = session.exec(
                    select(func.count())
                    .select_from(ZtpDiscovery)
                    .where(
                        ZtpDiscovery.node_id == node.id,
                        ZtpDiscovery.id != discovery.id,
                        ZtpDiscovery.review_status == ZtpReviewStatus.unreviewed,
                    )
                ).one()
                if not pending:
                    node.provision_status = NodeProvisionStatus.awaiting_device
                    node.updated_at = now
                    session.add(node)
            session.commit()
            logger.info(f"ZTP: {reviewed_by} rejected discovery {discovery.id} from {discovery.source_ip}")
            return self._response(session, discovery)
        finally:
            session.close()

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
    def _set_management_ip(session, node_id: int, ip: str) -> None:
        """Point the node's primary SSH connection at the IP it was discovered on, adding one if it has none."""
        connection = session.exec(
            select(ManagementConnection).where(
                ManagementConnection.node_id == node_id, ManagementConnection.primary.is_(True)
            )
        ).first()
        if connection is None:
            connection = ManagementConnection(node_id=node_id, primary=True)
        connection.target_ip = ip
        session.add(connection)

    def _response(self, session, discovery: ZtpDiscovery) -> ZtpDiscoveryResponse:
        response = ZtpDiscoveryResponse.model_validate(discovery)
        node = session.get(Node, discovery.node_id) if discovery.node_id is not None else None
        if node is not None:
            logical_node = session.get(LogicalNode, node.logical_node_id)
            response.node_hostname = logical_node.hostname if logical_node is not None else None
        asset = self._claimed_asset(session, node)
        if asset is not None:
            response.expected = ZtpExpected(
                asset_id=asset.id,
                serial_number=asset.serial_number,
                **{fact: _text(getattr(asset, fact)) for fact in _FACTS},
            )
        response.conflicts = self._conflicts(session, discovery, response.expected)
        return response

    @staticmethod
    def _claimed_asset(session, node: Node | None) -> Asset | None:
        if node is None or node.asset_ref_type != AssetRefType.asset:
            return None
        return session.get(Asset, node.asset_ref_id)

    @staticmethod
    def _conflicts(session, discovery: ZtpDiscovery, expected: ZtpExpected | None) -> list[ZtpConflict]:
        conflicts = []
        # Rejected reports are already dealt with; they do not cast doubt on this one.
        others = session.exec(
            select(ZtpDiscovery)
            .where(
                ZtpDiscovery.id != discovery.id,
                ZtpDiscovery.review_status != ZtpReviewStatus.rejected,
                (ZtpDiscovery.serial_number == discovery.serial_number)
                | (ZtpDiscovery.source_ip == discovery.source_ip),
            )
            .order_by(ZtpDiscovery.created_at.desc())
        ).all()
        for other in others:
            if other.serial_number == discovery.serial_number and other.source_ip != discovery.source_ip:
                conflicts.append(
                    ZtpConflict(
                        kind=ZtpConflictKind.serial_on_other_ip,
                        message=f"{other.source_ip} also says it is {other.serial_number}",
                        discovery_id=other.id,
                    )
                )
            elif other.source_ip == discovery.source_ip and other.serial_number != discovery.serial_number:
                conflicts.append(
                    ZtpConflict(
                        kind=ZtpConflictKind.ip_with_other_serial,
                        message=f"{other.source_ip} has also said it is {other.serial_number}",
                        discovery_id=other.id,
                    )
                )

        if expected is not None:
            if expected.serial_number != discovery.serial_number:
                conflicts.append(
                    ZtpConflict(
                        kind=ZtpConflictKind.fact_mismatch,
                        message=f"serial_number: reported {discovery.serial_number}, "
                        f"asset has {expected.serial_number}",
                    )
                )
            for fact in _FACTS:
                reported, known = getattr(discovery, fact), getattr(expected, fact)
                if reported and known and reported.casefold() != known.casefold():
                    conflicts.append(
                        ZtpConflict(
                            kind=ZtpConflictKind.fact_mismatch,
                            message=f"{fact}: reported {reported}, asset has {known}",
                        )
                    )
        return conflicts


def _text(value) -> str | None:
    return None if value is None else str(value)
