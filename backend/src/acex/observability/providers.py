from typing import Callable, List, Optional, Protocol

from sqlmodel import select

from acex.models.node import Node
from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.regions import SiteRegionAssignment
from acex.observability.components.base import TelemetryComponent
from acex.observability.components.icmp_ping import IcmpPingTelemetry
from acex.observability.components.snmp import SnmpTelemetry


Provider = Callable[["object"], List[TelemetryComponent]]


class _NodeComponentFactory(Protocol):
    def __call__(
        self,
        *,
        node_id: int,
        hostname: str,
        target_ip: str,
        site: Optional[str] = None,
        region: Optional[str] = None,
    ) -> TelemetryComponent: ...


def _per_node_provider(
    db_manager,
    component_cls: _NodeComponentFactory,
) -> List[TelemetryComponent]:
    """
    Build one component per node-instance (per region when assigned).
    Shared logic for any TelemetryComponent that maps 1-to-1 with a
    management IP and inherits site/region tags.
    """
    session = next(db_manager.get_session())
    try:
        nodes = session.exec(select(Node)).all()
        if not nodes:
            return []

        ln_ids = [n.logical_node_id for n in nodes]
        ln_map = {
            ln.id: ln
            for ln in session.exec(select(LogicalNode).where(LogicalNode.id.in_(ln_ids))).all()
        }

        unique_sites = list({ln.site for ln in ln_map.values() if ln.site})
        site_region_map: dict[str, list[str]] = {}
        if unique_sites:
            assignments = session.exec(
                select(SiteRegionAssignment).where(SiteRegionAssignment.site_name.in_(unique_sites))
            ).all()
            for a in assignments:
                site_region_map.setdefault(a.site_name, []).append(a.region_name)

        node_ids = [n.id for n in nodes]
        conns = session.exec(
            select(ManagementConnection).where(ManagementConnection.node_id.in_(node_ids))
        ).all()
        ip_map: dict[int, str] = {}
        for c in conns:
            if not c.target_ip:
                continue
            if c.node_id not in ip_map or c.primary:
                ip_map[c.node_id] = c.target_ip

        components: List[TelemetryComponent] = []
        for n in nodes:
            ln = ln_map.get(n.logical_node_id)
            ip = ip_map.get(n.id)
            if not ip or not ln:
                continue
            regions = site_region_map.get(ln.site, []) if ln.site else []
            if regions:
                for region in regions:
                    components.append(component_cls(
                        node_id=n.id, hostname=ln.hostname, target_ip=ip,
                        site=ln.site, region=region,
                    ))
            else:
                components.append(component_cls(
                    node_id=n.id, hostname=ln.hostname, target_ip=ip, site=ln.site,
                ))
        return components
    finally:
        session.close()


def icmp_ping_provider(db_manager) -> List[TelemetryComponent]:
    return _per_node_provider(db_manager, IcmpPingTelemetry)


def snmp_provider(db_manager, credential_manager=None) -> List[TelemetryComponent]:
    def _factory(*, node_id, hostname, target_ip, site=None, region=None) -> TelemetryComponent:
        community = "public"
        if credential_manager is not None and site is not None:
            community = credential_manager.get_site_community(site)
        return SnmpTelemetry(
            node_id=node_id, hostname=hostname, target_ip=target_ip,
            site=site, region=region, community=community,
        )
    return _per_node_provider(db_manager, _factory)
