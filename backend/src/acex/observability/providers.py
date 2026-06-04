from typing import Callable, List

from acex.models.node import Node
from acex.models.logical_node import LogicalNode
from acex.models.management_connections import ManagementConnection
from acex.models.regions import SiteRegionAssignment
from acex.observability.components.base import TelemetryComponent
from acex.observability.components.icmp_ping import IcmpPingTelemetry


Provider = Callable[["object"], List[TelemetryComponent]]


def icmp_ping_provider(db_manager) -> List[TelemetryComponent]:
    """
    Yield one IcmpPingTelemetry per node-instance that has a
    management IP. Nodes without any management connection are skipped.
    """
    session = next(db_manager.get_session())
    try:
        nodes = session.query(Node).all()
        if not nodes:
            return []

        ln_ids = [n.logical_node_id for n in nodes]
        ln_map = {
            ln.id: ln
            for ln in session.query(LogicalNode)
            .filter(LogicalNode.id.in_(ln_ids))
            .all()
        }

        unique_sites = list({ln.site for ln in ln_map.values() if ln.site})
        site_region_map: dict[str, str] = {}
        if unique_sites:
            assignments = (
                session.query(SiteRegionAssignment)
                .filter(SiteRegionAssignment.site_name.in_(unique_sites))
                .all()
            )
            for a in assignments:
                site_region_map.setdefault(a.site_name, a.region_name)

        node_ids = [n.id for n in nodes]
        conns = (
            session.query(ManagementConnection)
            .filter(ManagementConnection.node_id.in_(node_ids))
            .all()
        )
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
            components.append(
                IcmpPingTelemetry(
                    node_id=n.id,
                    hostname=ln.hostname,
                    target_ip=ip,
                    site=ln.site,
                    region=site_region_map.get(ln.site) if ln.site else None,
                )
            )
        return components
    finally:
        session.close()
