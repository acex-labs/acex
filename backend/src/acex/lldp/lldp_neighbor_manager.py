import hashlib
import json
from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException

from acex.models.lldp_neighbor import (
    LldpNeighbor,
    LldpNeighborUpload,
    LldpNeighborResponse,
)
from acex.models.node import Node
from acex.models.logical_node import LogicalNode


class LldpNeighborManager:

    def __init__(self, db_manager):
        self.db = db_manager

    def _resolve_remote_node(self, session, remote_device: str) -> Optional[int]:
        """Try to match remote_device hostname to a node in inventory.

        Tries exact match first, then strips domain suffix
        (e.g. 'switch2.example.com' -> 'switch2').
        """
        # Try exact match first
        ln = (
            session.query(LogicalNode)
            .filter(LogicalNode.hostname == remote_device)
            .first()
        )
        # Fallback: strip domain part
        if not ln and '.' in remote_device:
            short_name = remote_device.split('.')[0]
            ln = (
                session.query(LogicalNode)
                .filter(LogicalNode.hostname == short_name)
                .first()
            )
        if not ln:
            return None
        node = (
            session.query(Node)
            .filter(Node.logical_node_id == ln.id)
            .first()
        )
        return node.id if node else None

    def _hash_neighbor_set(self, payload: LldpNeighborUpload) -> str:
        """Deterministic hash of the full neighbor set for dedup."""
        entries = sorted(
            [
                {
                    "local_interface": n.local_interface,
                    "remote_device": n.remote_device,
                    "remote_interface": n.remote_interface,
                    "discovery_protocol": n.discovery_protocol,
                }
                for n in payload.neighbors
            ],
            key=lambda x: (x["local_interface"], x["remote_device"]),
        )
        blob = json.dumps(entries, sort_keys=True)
        return hashlib.md5(blob.encode()).hexdigest()

    def upload_neighbors(self, payload: LldpNeighborUpload) -> dict:
        session = next(self.db.get_session())
        try:
            new_hash = self._hash_neighbor_set(payload)

            # Dedup: check if latest hash for this node is the same
            latest = (
                session.query(LldpNeighbor)
                .filter(LldpNeighbor.node_instance_id == payload.node_instance_id)
                .order_by(LldpNeighbor.collected_at.desc())
                .first()
            )
            if latest and latest.hash == new_hash:
                # Re-resolve any unresolved remote_node_ids
                unresolved = (
                    session.query(LldpNeighbor)
                    .filter(
                        LldpNeighbor.node_instance_id == payload.node_instance_id,
                        LldpNeighbor.remote_node_id.is_(None),
                    )
                    .all()
                )
                updated = 0
                for row in unresolved:
                    resolved = self._resolve_remote_node(session, row.remote_device)
                    if resolved:
                        row.remote_node_id = resolved
                        updated += 1
                if updated:
                    session.commit()
                raise HTTPException(
                    status_code=409,
                    detail="Neighbor set unchanged",
                )

            # Delete old entries for this node, insert fresh set
            session.query(LldpNeighbor).filter(
                LldpNeighbor.node_instance_id == payload.node_instance_id
            ).delete()

            now = datetime.utcnow()
            for entry in payload.neighbors:
                remote_node_id = self._resolve_remote_node(session, entry.remote_device)
                neighbor = LldpNeighbor(
                    node_instance_id=payload.node_instance_id,
                    local_interface=entry.local_interface,
                    remote_device=entry.remote_device,
                    remote_interface=entry.remote_interface,
                    remote_node_id=remote_node_id,
                    discovery_protocol=entry.discovery_protocol,
                    hash=new_hash,
                    collected_at=now,
                )
                session.add(neighbor)

            session.commit()
            return {
                "status": "ok",
                "node_instance_id": payload.node_instance_id,
                "count": len(payload.neighbors),
                "hash": new_hash,
            }
        finally:
            session.close()

    def get_neighbors(self, node_instance_id: int) -> List[LldpNeighborResponse]:
        session = next(self.db.get_session())
        try:
            rows = (
                session.query(LldpNeighbor)
                .filter(LldpNeighbor.node_instance_id == node_instance_id)
                .order_by(LldpNeighbor.local_interface)
                .all()
            )
            return [LldpNeighborResponse.model_validate(r) for r in rows]
        finally:
            session.close()

    def get_reverse_neighbors(self, node_instance_id: int) -> List[LldpNeighborResponse]:
        """Who sees this node as a neighbor."""
        session = next(self.db.get_session())
        try:
            rows = (
                session.query(LldpNeighbor)
                .filter(LldpNeighbor.remote_node_id == node_instance_id)
                .order_by(LldpNeighbor.node_instance_id)
                .all()
            )
            return [LldpNeighborResponse.model_validate(r) for r in rows]
        finally:
            session.close()

    def get_topology(
        self,
        site: Optional[str] = None,
        node_id: Optional[int] = None,
        hops: int = 1,
    ) -> dict:
        """Graph of nodes and links. Returns { nodes, edges }.

        Scope (mutually exclusive):
          - site: all links reported by nodes on that site
          - node_id + hops: BFS traversal N hops out from a node
        """
        session = next(self.db.get_session())
        try:
            if node_id is not None:
                rows = self._collect_hops(session, node_id, hops)
            elif site is not None:
                rows = (
                    session.query(LldpNeighbor)
                    .join(Node, LldpNeighbor.node_instance_id == Node.id)
                    .join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                    .filter(LogicalNode.site.ilike(site))
                    .all()
                )
            else:
                return {"nodes": [], "edges": []}

            return self._build_graph(session, rows)
        finally:
            session.close()

    def _collect_hops(self, session, start_node_id: int, max_hops: int) -> list:
        """BFS from start_node_id, collecting neighbor rows up to max_hops."""
        visited_nodes = {start_node_id}
        frontier = {start_node_id}
        all_rows = []

        for _ in range(max_hops):
            if not frontier:
                break
            rows = (
                session.query(LldpNeighbor)
                .filter(LldpNeighbor.node_instance_id.in_(frontier))
                .all()
            )
            all_rows.extend(rows)
            next_frontier = set()
            for r in rows:
                if r.remote_node_id and r.remote_node_id not in visited_nodes:
                    next_frontier.add(r.remote_node_id)
                    visited_nodes.add(r.remote_node_id)
            frontier = next_frontier

        return all_rows

    def _build_graph(self, session, rows: list) -> dict:
        """Convert neighbor rows into { nodes, edges } graph with deduplicated links."""
        nodes_map = {}
        seen_edges = set()
        edges = []

        for r in rows:
            # Source node (always known)
            if r.node_instance_id not in nodes_map:
                src_node = session.get(Node, r.node_instance_id)
                src_ln = session.get(LogicalNode, src_node.logical_node_id) if src_node else None
                nodes_map[r.node_instance_id] = {
                    "id": r.node_instance_id,
                    "label": src_ln.hostname if src_ln else f"node-{r.node_instance_id}",
                    "in_inventory": True,
                }

            # Remote node
            if r.remote_node_id:
                if r.remote_node_id not in nodes_map:
                    rem_node = session.get(Node, r.remote_node_id)
                    rem_ln = session.get(LogicalNode, rem_node.logical_node_id) if rem_node else None
                    nodes_map[r.remote_node_id] = {
                        "id": r.remote_node_id,
                        "label": rem_ln.hostname if rem_ln else f"node-{r.remote_node_id}",
                        "in_inventory": True,
                    }
                target_id = r.remote_node_id
            else:
                key = f"unknown:{r.remote_device}"
                if key not in nodes_map:
                    nodes_map[key] = {
                        "id": key,
                        "label": r.remote_device,
                        "in_inventory": False,
                    }
                target_id = key

            # Deduplicate bidirectional links:
            # A reports Gi0/1 -> B:Gi0/2, B reports Gi0/2 -> A:Gi0/1
            # Normalize: sorted node pair + sorted interface pair
            a, b = str(r.node_instance_id), str(target_id)
            side_a = f"{a}:{r.local_interface}"
            side_b = f"{b}:{r.remote_interface}"
            edge_key = tuple(sorted([side_a, side_b]))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "source": r.node_instance_id,
                    "target": target_id,
                    "source_interface": r.local_interface,
                    "target_interface": r.remote_interface,
                    "discovery_protocol": r.discovery_protocol,
                })

        return {
            "nodes": list(nodes_map.values()),
            "edges": edges,
        }

    def get_neighbors_by_site(self, site: str) -> List[LldpNeighborResponse]:
        """All neighbor links for nodes on a given site."""
        session = next(self.db.get_session())
        try:
            rows = (
                session.query(LldpNeighbor)
                .join(Node, LldpNeighbor.node_instance_id == Node.id)
                .join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                .filter(LogicalNode.site.ilike(site))
                .order_by(LldpNeighbor.node_instance_id, LldpNeighbor.local_interface)
                .all()
            )
            return [LldpNeighborResponse.model_validate(r) for r in rows]
        finally:
            session.close()
