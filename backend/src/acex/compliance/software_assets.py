from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Literal

from acex.compliance.software import SoftwareCheck
from acex.models import Asset, AssetCluster, AssetClusterLink, LogicalNode, Node
from acex_devkit.models.compliance import SoftwareAssetList, SoftwareAssetRow, SoftwareStatus
from acex_devkit.models.node_response import AssetRefType
from acex_devkit.models.os_version import OsVersionScheme
from acex_devkit.models.platform import OS, Vendor
from fastapi import HTTPException, Query
from sqlalchemy import select

# The ones to work on first: what is not on an approved version, then what nothing measures, then the compliant.
SEVERITY = {
    status: order
    for order, status in enumerate(
        [
            SoftwareStatus.not_allowed,
            SoftwareStatus.unknown_version,
            SoftwareStatus.no_policy,
            SoftwareStatus.accepted,
            SoftwareStatus.golden,
        ]
    )
}


@dataclass(frozen=True, slots=True)
class AssetOfNode:
    """An asset of a node as the inventory holds it, with the little of the node that the list shows."""

    asset_id: int
    vendor: Vendor
    serial_number: str
    hardware_model: str
    os: OS
    os_version: str | None
    node_id: int
    hostname: str | None
    site: str | None
    #: The cluster the asset is a member of; None for an asset that is a node on its own.
    cluster: str | None


@dataclass(frozen=True, slots=True)
class Measured:
    asset: AssetOfNode
    status: SoftwareStatus
    golden_version: str | None
    regions: list[str]


def folded(value) -> str:
    """A name or an enum as text to compare ignoring case; nothing as empty."""
    return "" if value is None else str(value).casefold()


@lru_cache(maxsize=4096)
def version_order(os: OS, version: str | None):
    """Versions of one OS by number where its scheme can tell; those it can't by name; those not reported last."""
    if version is None:
        return (str(os), 2, "")
    scheme = OsVersionScheme.for_os(os)
    parsed = scheme.normalize(version) if scheme and scheme.accepts(version) else None
    # The version's own sort_key, a plain tuple: sorting by the objects rebuilds that tuple on every comparison.
    return (str(os), 0, parsed.sort_key) if parsed is not None else (str(os), 1, version)


SORT_KEYS = {
    "status": lambda m: SEVERITY[m.status],
    "hostname": lambda m: folded(m.asset.hostname),
    "site": lambda m: folded(m.asset.site),
    "hardware_model": lambda m: folded(m.asset.hardware_model),
    "os_version": lambda m: version_order(m.asset.os, m.asset.os_version),
    "serial_number": lambda m: folded(m.asset.serial_number),
}


class SoftwareAssets:
    """Software compliance asset by asset: every asset of every node, to filter, search and sort.

    It counts the same assets as the compliance of the installation, each asset of a cluster on its own, and reads
    the status from the same check. It reads the software policy and the inventory, never a node's configuration,
    so it answers at once however many nodes there are: the nodes and their assets are read in two queries, and
    what the page asks for is decided in memory. An asset no node has is not listed: nothing is measured of it.
    """

    def __init__(self, db, check: SoftwareCheck, regions):
        self.db = db
        self.check = check
        self.regions = regions

    def query(
        self,
        status: Annotated[list[SoftwareStatus] | None, Query()] = None,
        site: str | None = None,
        region: str | None = None,
        q: str | None = None,
        sort: str = "status",
        order: Literal["asc", "desc"] = "asc",
        limit: Annotated[int, Query(ge=1, le=1000)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> SoftwareAssetList:
        """The assets, filtered, searched and sorted, a page of them.

        `site` and `region` match whole names, ignoring case. `q` is one search text matched, ignoring case, as a
        contains against hostname, site, serial number, hardware model, vendor, OS, running version and cluster.
        Every filter narrows the result together with the others. `status` may be given more than once. Without a
        `sort` the assets not on an approved version come first.
        """
        if sort not in SORT_KEYS:
            raise HTTPException(status_code=400, detail=f"Invalid sort field '{sort}'. Valid: {sorted(SORT_KEYS)}")

        in_scope = [m for m in self.measure() if self.matches(m, site, region, q)]
        counts = Counter(m.status for m in in_scope)
        chosen = [m for m in in_scope if not status or m.status in status]
        # Ties in the order go by hostname and then asset, so a page is the same page each time it is asked for.
        chosen.sort(
            key=lambda m: (SORT_KEYS[sort](m), folded(m.asset.hostname), m.asset.asset_id), reverse=order == "desc"
        )
        return SoftwareAssetList(
            items=[self.row(m) for m in chosen[offset : offset + limit]],
            total=len(chosen),
            limit=limit,
            offset=offset,
            status_counts={s: counts.get(s, 0) for s in SoftwareStatus},
        )

    def measure(self) -> list[Measured]:
        """Every asset of every node against the software policy as it stands now, read once."""
        approved = self.check.approved()
        assigned = defaultdict(list)
        for assignment in self.regions.list_assignments():
            assigned[assignment.site_name].append(assignment.region_name)
        # Sorted once for each site, not for each asset; an asset with no site, or a site in no region, has none.
        regions_of = {site: sorted(names) for site, names in assigned.items()}
        measured = []
        for asset in self.read():
            status, golden_version = self.check.status(asset, approved)
            measured.append(Measured(asset, status, golden_version, regions_of.get(asset.site, [])))
        return measured

    def read(self) -> list[AssetOfNode]:
        """The assets of every node: a node's own asset, and each member of a node's cluster."""
        asset_columns = (Asset.id, Asset.vendor, Asset.serial_number, Asset.hardware_model, Asset.os, Asset.os_version)
        node_columns = (Node.id, LogicalNode.hostname, LogicalNode.site)
        own = (
            select(*asset_columns, *node_columns)
            .select_from(Node)
            .join(LogicalNode, LogicalNode.id == Node.logical_node_id)
            .join(Asset, Asset.id == Node.asset_ref_id)
            .where(Node.asset_ref_type == AssetRefType.asset)
        )
        members = (
            select(*asset_columns, *node_columns, AssetCluster.name)
            .select_from(Node)
            .join(LogicalNode, LogicalNode.id == Node.logical_node_id)
            .join(AssetCluster, AssetCluster.id == Node.asset_ref_id)
            .join(AssetClusterLink, AssetClusterLink.cluster_id == AssetCluster.id)
            .join(Asset, Asset.id == AssetClusterLink.asset_id)
            .where(Node.asset_ref_type == AssetRefType.asset_cluster)
        )
        session = next(self.db.get_session())
        try:
            own_rows = session.execute(own).all()
            member_rows = session.execute(members).all()
        finally:
            session.close()
        return [AssetOfNode(*row, None) for row in own_rows] + [AssetOfNode(*row) for row in member_rows]

    @staticmethod
    def matches(m: Measured, site, region, q) -> bool:
        """Whether the asset is in what every filter but the status asks for."""
        a = m.asset
        if site and folded(site) != folded(a.site):
            return False
        if region and folded(region) not in (folded(r) for r in m.regions):
            return False
        text = folded((q or "").strip())
        if text:
            fields = (a.hostname, a.site, a.serial_number, a.hardware_model, a.vendor, a.os, a.os_version, a.cluster)
            if not any(text in folded(f) for f in fields):
                return False
        return True

    @staticmethod
    def row(m: Measured) -> SoftwareAssetRow:
        a = m.asset
        return SoftwareAssetRow(
            asset_id=a.asset_id,
            vendor=a.vendor,
            serial_number=a.serial_number,
            hardware_model=a.hardware_model,
            os=a.os,
            os_version=a.os_version,
            status=m.status,
            golden_version=m.golden_version,
            node_id=a.node_id,
            hostname=a.hostname,
            site=a.site,
            regions=m.regions,
            cluster=a.cluster,
        )
