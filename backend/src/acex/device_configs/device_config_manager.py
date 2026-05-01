from datetime import datetime
import base64
import hashlib
from sqlalchemy import func
from sqlmodel import SQLModel
from typing import Tuple, Optional
from fastapi import HTTPException
from enum import Enum

from acex.models import DeviceConfig, StoredDeviceConfig, DeviceConfigResponse
from acex.models.node import Node
from acex.models.logical_node import LogicalNode
from acex.plugins.neds.manager import NEDManager

class ConfigOutput(str, Enum):
    PARSED = "parsed"
    RENDERED = "rendered"



class DeviceConfigManager:
    """
    This class manages input and retreival of 
    device configurations. 
    """

    def __init__(self, db_manager, inventory=None):
        self.db = db_manager
        self.inventory = inventory
        self.neds = NEDManager()

    async def _get_ned(self, node_instance):
        # Hitta asset baserat på node instance id.
        return self.neds.get_driver_instance(node_instance.asset.ned_id)


    def list_config_hashes(
        self, 
        node_instance_id: str,
        point_in_time: datetime = None,
        limit: int = 100,
        ) -> list: 

        session = next(self.db.get_session())
        try:
            # Bygg upp query med specifika kolumner (exkluderar content)
            query = session.query(
                StoredDeviceConfig.id,
                StoredDeviceConfig.hash,
                StoredDeviceConfig.created_at,
                StoredDeviceConfig.node_instance_id
            ).filter(
                StoredDeviceConfig.node_instance_id == node_instance_id
            )

            
            if point_in_time is not None:
                query = query.filter(StoredDeviceConfig.created_at <= point_in_time)
                
            results = query.order_by(StoredDeviceConfig.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": result.id,
                    "hash": result.hash,
                    "created_at": result.created_at,
                    "node_instance_id": result.node_instance_id
                }
                for result in results
            ]
        finally:
            session.close()

    def list_changes(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        site: Optional[str] = None,
        role: Optional[str] = None,
        hostname: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 500,
    ) -> list:
        """
        Return config snapshots across all node instances within the
        optional [since, until] window, each enriched with the previous
        snapshot for the same node (computed over the full history, not
        just the window) so the caller can diff `previous_hash → hash`
        directly.

        Filters (`site`, `role`, `hostname`) match against the corresponding
        LogicalNode fields as case-insensitive substring matches.
        `sort_by` accepts `created_at | hostname | site | role`; `sort_order`
        is `asc | desc`. Time-based sort runs in SQL; node-attribute sort
        runs in Python over the limited result.
        """
        until_value = until or datetime.utcnow()
        sort_order_norm = "asc" if str(sort_order).lower() == "asc" else "desc"

        session = next(self.db.get_session())
        try:
            # Pre-resolve matching node ids if any node-attribute filter is set
            matching_ids: Optional[list[str]] = None
            if site or role or hostname:
                q = session.query(Node.id).join(
                    LogicalNode, LogicalNode.id == Node.logical_node_id,
                )
                if site:
                    q = q.filter(LogicalNode.site.ilike(f"%{site}%"))
                if role:
                    q = q.filter(LogicalNode.role.ilike(f"%{role}%"))
                if hostname:
                    q = q.filter(LogicalNode.hostname.ilike(f"%{hostname}%"))
                matching_ids = [str(r.id) for r in q.all()]
                if not matching_ids:
                    return []

            prev_hash = func.lag(StoredDeviceConfig.hash).over(
                partition_by=StoredDeviceConfig.node_instance_id,
                order_by=StoredDeviceConfig.created_at,
            ).label("previous_hash")
            prev_created = func.lag(StoredDeviceConfig.created_at).over(
                partition_by=StoredDeviceConfig.node_instance_id,
                order_by=StoredDeviceConfig.created_at,
            ).label("previous_created_at")

            sub = session.query(
                StoredDeviceConfig.id,
                StoredDeviceConfig.hash,
                StoredDeviceConfig.created_at,
                StoredDeviceConfig.node_instance_id,
                prev_hash,
                prev_created,
            ).filter(
                StoredDeviceConfig.created_at <= until_value,
            ).subquery()

            outer = session.query(sub)
            if since is not None:
                outer = outer.filter(sub.c.created_at >= since)
            if matching_ids is not None:
                outer = outer.filter(sub.c.node_instance_id.in_(matching_ids))

            time_order = sub.c.created_at.asc() if sort_order_norm == "asc" else sub.c.created_at.desc()
            outer = outer.order_by(time_order)
            rows = outer.limit(limit).all()

            # Batch-resolve hostname/site/role per node_instance_id
            node_id_strs = list({r.node_instance_id for r in rows})
            int_ids = []
            for nid in node_id_strs:
                try:
                    int_ids.append(int(nid))
                except (TypeError, ValueError):
                    pass

            meta_map: dict[str, dict] = {}
            if int_ids:
                nodes = session.query(Node).filter(Node.id.in_(int_ids)).all()
                ln_ids = [n.logical_node_id for n in nodes]
                logical_nodes = (
                    session.query(LogicalNode).filter(LogicalNode.id.in_(ln_ids)).all()
                    if ln_ids else []
                )
                ln_map = {ln.id: ln for ln in logical_nodes}
                for n in nodes:
                    ln = ln_map.get(n.logical_node_id)
                    meta_map[str(n.id)] = {
                        "hostname": ln.hostname if ln else None,
                        "site": ln.site if ln else None,
                        "role": ln.role if ln else None,
                    }

            result = [
                {
                    "id": r.id,
                    "node_instance_id": r.node_instance_id,
                    "hostname": (meta_map.get(r.node_instance_id) or {}).get("hostname"),
                    "site": (meta_map.get(r.node_instance_id) or {}).get("site"),
                    "role": (meta_map.get(r.node_instance_id) or {}).get("role"),
                    "hash": r.hash,
                    "created_at": r.created_at,
                    "previous_hash": r.previous_hash,
                    "previous_created_at": r.previous_created_at,
                }
                for r in rows
            ]

            if sort_by in ("hostname", "site", "role"):
                reverse = sort_order_norm == "desc"
                # Stable sort: items with same key keep DB order (created_at)
                result.sort(key=lambda x: (x.get(sort_by) or "").lower(), reverse=reverse)

            return result
        finally:
            session.close()


    def get_config_by_hash(
        self,
        node_instance_id:str,
        hash:str
        ) -> StoredDeviceConfig:

        session = next(self.db.get_session())
        try:
            existing = session.query(StoredDeviceConfig).filter(
                StoredDeviceConfig.hash == hash
            ).first()
            return existing
        finally:
            session.close()


    async def get_latest_config(
        self,
        node_instance_id:str,
        output: ConfigOutput = ConfigOutput.RENDERED
        ) -> DeviceConfigResponse:

        session = next(self.db.get_session())
        try:
            existing = session.query(StoredDeviceConfig).filter(
                StoredDeviceConfig.node_instance_id == node_instance_id
            ).order_by(StoredDeviceConfig.created_at.desc()).first()


            if output == ConfigOutput.PARSED:
                # Get ned from node_instance.asset
                node_instance = await self.inventory.node_instances.get(node_instance_id)
                ned = await self._get_ned(node_instance)

                if ned is not None:
                    existing.content = ned.parse(existing.content)
                else:
                    existing.content = ""
                return existing
            else:
                return existing
        finally:
            session.close()


    async def upload_config(
        self,
        payload: DeviceConfig,
        ) -> StoredDeviceConfig:
        # Normalize: strip non-intent data and mask secrets via NED
        node_instance = await self.inventory.node_instances.get(payload.node_instance_id)
        ned = await self._get_ned(node_instance)

        raw = base64.b64decode(payload.content).decode("utf-8")

        if ned is not None:
            cleaned = ned.normalize(raw)
            cleaned = ned.mask(cleaned)
        else:
            cleaned = raw

        content = cleaned
        config_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

        # spara till db med hash
        session = next(self.db.get_session())
        try:
            # Skippa om senaste configen har samma hash (ingen faktisk ändring)
            latest = session.query(StoredDeviceConfig).filter(
                StoredDeviceConfig.node_instance_id == payload.node_instance_id
            ).order_by(StoredDeviceConfig.created_at.desc()).first()

            if latest and latest.hash == config_hash:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Config not changed since last time",
                        "last_hash": config_hash,
                        "last_change": str(latest.created_at),
                        "node_instance_id": payload.node_instance_id
                    }
                )

            save_this = StoredDeviceConfig(
                node_instance_id=payload.node_instance_id,
                hash=config_hash,
                content=content
            )

            session.add(save_this)
            session.commit()
            session.refresh(save_this)
            return save_this
        finally:
            session.close()

