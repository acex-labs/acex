"""What reviewing a set of discoveries needs to know, loaded in a few queries."""

from dataclasses import dataclass, field

from acex.models.asset import Asset
from acex.models.job import Job
from acex.models.logical_node import LogicalNode
from acex.models.node import AssetRefType, Node, NodeProvisionStatus
from acex.models.ztp_discovery import ZtpDiscovery
from acex.models.ztp_method import ZtpMethodRow
from acex_devkit.models.ztp import ZtpConflict, ZtpConflictKind, ZtpReviewStatus
from sqlmodel import or_, select


@dataclass
class ReviewContext:
    #: Discoveries that are not rejected and share a serial or an IP with one being reviewed.
    related: list[ZtpDiscovery] = field(default_factory=list)
    assets_by_serial: dict[str, list[Asset]] = field(default_factory=dict)
    assets_by_id: dict[int, Asset] = field(default_factory=dict)
    nodes_by_asset: dict[int, Node] = field(default_factory=dict)
    hostnames: dict[int, str] = field(default_factory=dict)
    #: The NED chosen for the method of each discovery's job.
    neds_by_job: dict[int, str | None] = field(default_factory=dict)

    @classmethod
    def load(cls, session, discoveries: list[ZtpDiscovery]) -> "ReviewContext":
        ctx = cls()
        if not discoveries:
            return ctx
        serials = {d.serial_number for d in discoveries}
        ips = {d.source_ip for d in discoveries}
        asset_ids = {d.asset_id for d in discoveries if d.asset_id is not None}
        job_ids = {d.job_id for d in discoveries if d.job_id is not None}

        ctx.related = list(
            session.exec(
                select(ZtpDiscovery)
                .where(
                    ZtpDiscovery.review_status != ZtpReviewStatus.rejected,
                    or_(ZtpDiscovery.serial_number.in_(serials), ZtpDiscovery.source_ip.in_(ips)),
                )
                .order_by(ZtpDiscovery.created_at.desc(), ZtpDiscovery.id.desc())
            ).all()
        )

        asset_filter = or_(Asset.serial_number.in_(serials), Asset.id.in_(asset_ids))
        for asset in session.exec(select(Asset).where(asset_filter).order_by(Asset.id)).all():
            ctx.assets_by_id[asset.id] = asset
            if asset.serial_number in serials:
                ctx.assets_by_serial.setdefault(asset.serial_number, []).append(asset)

        nodes = session.exec(
            select(Node).where(Node.asset_ref_type == AssetRefType.asset, Node.asset_ref_id.in_(ctx.assets_by_id))
        ).all()
        ctx.nodes_by_asset = {node.asset_ref_id: node for node in nodes}
        logical_ids = {node.logical_node_id for node in nodes}
        ctx.hostnames = {
            ln.id: ln.hostname for ln in session.exec(select(LogicalNode).where(LogicalNode.id.in_(logical_ids))).all()
        }

        neds = {row.method: row.ned for row in session.exec(select(ZtpMethodRow)).all()}
        for job in session.exec(select(Job).where(Job.id.in_(job_ids))).all():
            ctx.neds_by_job[job.id] = neds.get((job.data or {}).get("method"))
        return ctx

    def assets_with_serial(self, discovery: ZtpDiscovery) -> list[Asset]:
        return self.assets_by_serial.get(discovery.serial_number, [])

    def asset_of(self, discovery: ZtpDiscovery) -> Asset | None:
        """The asset the discovery was approved as, or else the only asset with its serial."""
        if discovery.asset_id is not None:
            return self.assets_by_id.get(discovery.asset_id)
        matches = self.assets_with_serial(discovery)
        return matches[0] if len(matches) == 1 else None

    def node_of(self, discovery: ZtpDiscovery) -> Node | None:
        asset = self.asset_of(discovery)
        return self.nodes_by_asset.get(asset.id) if asset is not None else None

    def hostname_of(self, node: Node) -> str | None:
        return self.hostnames.get(node.logical_node_id)

    def ned_for(self, discovery: ZtpDiscovery) -> str | None:
        return self.neds_by_job.get(discovery.job_id)

    def conflicts(self, discovery: ZtpDiscovery) -> list[ZtpConflict]:
        """What an administrator should look at before trusting the discovery."""
        conflicts = []
        # Rejected reports are already dealt with and not among the related ones.
        for other in self.related:
            same_serial = other.serial_number == discovery.serial_number
            same_ip = other.source_ip == discovery.source_ip
            if other.id == discovery.id or same_serial == same_ip:
                continue
            kind, verb = (
                (ZtpConflictKind.serial_on_other_ip, "also says")
                if same_serial
                else (ZtpConflictKind.ip_with_other_serial, "has also said")
            )
            message = f"{other.source_ip} {verb} it is {other.serial_number}"
            conflicts.append(ZtpConflict(kind=kind, message=message, discovery_id=other.id))

        node = self.node_of(discovery)
        if node is not None and node.provision_status == NodeProvisionStatus.provisioned:
            hostname = self.hostname_of(node) or f"node {node.id}"
            conflicts.append(
                ZtpConflict(
                    kind=ZtpConflictKind.serial_of_provisioned_node,
                    message=f"{discovery.serial_number} is provisioned as {hostname}; it may have been reset",
                    node_id=node.id,
                )
            )
        return conflicts
