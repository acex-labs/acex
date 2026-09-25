from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.node import Node
from acex.models.regions import SiteRegionAssignment
from acex.observability.components.base import TelemetryComponent
from acex.observability.components.icmp_ping import IcmpPingTelemetry
from acex.observability.components.snmp import SnmpTelemetry
from sqlmodel import select

# Stable reason codes for nodes a provider could not render.
NODE_NOT_FOUND = "node_not_found"
NO_LOGICAL_NODE = "no_logical_node"
NO_MANAGEMENT_IP = "no_management_ip"
COMPONENT_ERROR = "component_error"


@dataclass(frozen=True)
class SkippedNode:
    node_id: int
    reason: str
    detail: str | None = None


@dataclass
class ProviderResult:
    components: list[TelemetryComponent] = field(default_factory=list)
    skipped: list[SkippedNode] = field(default_factory=list)


# A provider takes the db manager plus optional keyword args
# (`node_ids`, `credential_manager`) and returns either a ProviderResult
# or — for legacy providers — a bare list of components.
Provider = Callable[..., ProviderResult | list[TelemetryComponent]]


class _NodeComponentFactory(Protocol):
    def __call__(
        self,
        *,
        node_id: int,
        hostname: str,
        target_ip: str,
        site: str | None = None,
        region: str | None = None,
    ) -> TelemetryComponent: ...


def _error_detail(exc: Exception) -> str:
    # HTTPException carries its message in `detail`; str() would prefix the status code.
    return str(getattr(exc, "detail", None) or exc) or type(exc).__name__


def _per_node_provider(
    db_manager,
    component_cls: _NodeComponentFactory,
    node_ids: Iterable[int] | None = None,
) -> ProviderResult:
    """
    Build one component per node-instance (per region when assigned).
    Shared logic for any TelemetryComponent that maps 1-to-1 with a
    management IP and inherits site/region tags.

    `node_ids=None` means every node (used for global views such as
    Grafana dashboards); otherwise only the given nodes are loaded, and
    any that cannot be rendered are reported in `ProviderResult.skipped`.
    """
    requested = set(node_ids) if node_ids is not None else None
    if requested is not None and not requested:
        return ProviderResult()

    session = next(db_manager.get_session())
    try:
        stmt = select(Node)
        if requested is not None:
            stmt = stmt.where(Node.id.in_(requested))
        nodes = session.exec(stmt).all()

        ln_ids = [n.logical_node_id for n in nodes]
        ln_map = (
            {ln.id: ln for ln in session.exec(select(LogicalNode).where(LogicalNode.id.in_(ln_ids))).all()}
            if ln_ids
            else {}
        )

        unique_sites = list({ln.site for ln in ln_map.values() if ln.site})
        site_region_map: dict[str, list[str]] = {}
        if unique_sites:
            assignments = session.exec(
                select(SiteRegionAssignment).where(SiteRegionAssignment.site_name.in_(unique_sites))
            ).all()
            for a in assignments:
                site_region_map.setdefault(a.site_name, []).append(a.region_name)

        found_ids = [n.id for n in nodes]
        conns = (
            session.exec(select(ManagementConnection).where(ManagementConnection.node_id.in_(found_ids))).all()
            if found_ids
            else []
        )
        ip_map: dict[int, str] = {}
        for c in conns:
            if not c.target_ip:
                continue
            if c.node_id not in ip_map or c.primary:
                ip_map[c.node_id] = c.target_ip
    finally:
        # Close before building components — factories may open their own
        # sessions (e.g. credential lookups).
        session.close()

    result = ProviderResult()
    if requested is not None:
        for missing in sorted(requested - set(found_ids)):
            result.skipped.append(SkippedNode(missing, NODE_NOT_FOUND))

    for n in nodes:
        ln = ln_map.get(n.logical_node_id)
        if not ln:
            result.skipped.append(SkippedNode(n.id, NO_LOGICAL_NODE))
            continue
        ip = ip_map.get(n.id)
        if not ip:
            result.skipped.append(SkippedNode(n.id, NO_MANAGEMENT_IP))
            continue

        regions = site_region_map.get(ln.site, [None]) if ln.site else [None]
        try:
            node_components = [
                component_cls(
                    node_id=n.id,
                    hostname=ln.hostname,
                    target_ip=ip,
                    site=ln.site,
                    region=region,
                )
                for region in regions
            ]
        except Exception as e:
            # One broken node (e.g. an undecryptable credential) must not
            # take down rendering for every other node.
            result.skipped.append(SkippedNode(n.id, COMPONENT_ERROR, _error_detail(e)))
            continue
        result.components.extend(node_components)

    return result


def icmp_ping_provider(db_manager, node_ids: Iterable[int] | None = None) -> ProviderResult:
    return _per_node_provider(db_manager, IcmpPingTelemetry, node_ids)


def snmp_provider(db_manager, node_ids: Iterable[int] | None = None, credential_manager=None) -> ProviderResult:
    def _factory(*, node_id, hostname, target_ip, site=None, region=None) -> TelemetryComponent:
        community = "public"
        if credential_manager is not None:
            node_community = credential_manager.get_node_community(node_id)
            if node_community is not None:
                community = node_community
            elif site is not None:
                community = credential_manager.get_site_community(site)
        return SnmpTelemetry(
            node_id=node_id,
            hostname=hostname,
            target_ip=target_ip,
            site=site,
            region=region,
            community=community,
        )

    return _per_node_provider(db_manager, _factory, node_ids)
