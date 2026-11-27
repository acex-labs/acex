import hashlib
import json
from datetime import UTC, datetime

from acex.models.lldp_neighbor import LldpNeighbor
from acex.models.logical_node import LogicalNode
from acex.models.node import Node
from acex_devkit.models.lldp_neighbor import LldpNeighborResponse, LldpNeighborUpload
from fastapi import HTTPException
from sqlmodel import delete, func, select


class LldpNeighborManager:
    def __init__(self, db_manager):
        self.db = db_manager

    @staticmethod
    def _find_logical_node(session, name: str) -> LogicalNode | None:
        """The logical node called ``name``: an exact match wins, else one that differs only in case or padding."""
        exact = session.exec(select(LogicalNode).where(LogicalNode.hostname == name).order_by(LogicalNode.id)).first()
        if exact:
            return exact
        return session.exec(
            select(LogicalNode)
            .where(func.lower(func.trim(LogicalNode.hostname)) == func.lower(name.strip()))
            .order_by(LogicalNode.id)
        ).first()

    def _resolve_remote_node(self, session, remote_device: str) -> int | None:
        """Try to match remote_device hostname to a node in inventory.

        Tries the full name first, then strips domain suffix
        (e.g. 'switch2.example.com' -> 'switch2'). A device may report its name
        in another case than the inventory holds ('CORE-SW1' for 'core-sw1').
        """
        ln = self._find_logical_node(session, remote_device)
        # Fallback: strip domain part
        if not ln and "." in remote_device:
            ln = self._find_logical_node(session, remote_device.split(".")[0])
        if not ln:
            return None
        node = session.exec(select(Node).where(Node.logical_node_id == ln.id)).first()
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
            latest = session.exec(
                select(LldpNeighbor)
                .where(LldpNeighbor.node_instance_id == payload.node_instance_id)
                .order_by(LldpNeighbor.collected_at.desc())
            ).first()
            if latest and latest.hash == new_hash:
                # Re-resolve any unresolved remote_node_ids
                unresolved = session.exec(
                    select(LldpNeighbor).where(
                        LldpNeighbor.node_instance_id == payload.node_instance_id,
                        LldpNeighbor.remote_node_id.is_(None),
                    )
                ).all()
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
            session.exec(delete(LldpNeighbor).where(LldpNeighbor.node_instance_id == payload.node_instance_id))

            now = datetime.now(UTC)
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

    def get_neighbors(self, node_instance_id: int) -> list[LldpNeighborResponse]:
        session = next(self.db.get_session())
        try:
            rows = session.exec(
                select(LldpNeighbor)
                .where(LldpNeighbor.node_instance_id == node_instance_id)
                .order_by(LldpNeighbor.local_interface)
            ).all()
            return [LldpNeighborResponse.model_validate(r) for r in rows]
        finally:
            session.close()

    def get_reverse_neighbors(self, node_instance_id: int) -> list[LldpNeighborResponse]:
        """Who sees this node as a neighbor."""
        session = next(self.db.get_session())
        try:
            rows = session.exec(
                select(LldpNeighbor)
                .where(LldpNeighbor.remote_node_id == node_instance_id)
                .order_by(LldpNeighbor.node_instance_id)
            ).all()
            return [LldpNeighborResponse.model_validate(r) for r in rows]
        finally:
            session.close()

    def get_neighbors_by_site(self, site: str) -> list[LldpNeighborResponse]:
        """All neighbor links for nodes on a given site."""
        session = next(self.db.get_session())
        try:
            rows = session.exec(
                select(LldpNeighbor)
                .join(Node, LldpNeighbor.node_instance_id == Node.id)
                .join(LogicalNode, Node.logical_node_id == LogicalNode.id)
                .where(LogicalNode.site.ilike(site))
                .order_by(LldpNeighbor.node_instance_id, LldpNeighbor.local_interface)
            ).all()
            return [LldpNeighborResponse.model_validate(r) for r in rows]
        finally:
            session.close()
