from datetime import datetime
import base64
import hashlib
from sqlmodel import SQLModel
from typing import Tuple, Optional
from fastapi import HTTPException
from enum import Enum

from acex.models import DeviceConfig, StoredDeviceConfig, DeviceConfigResponse
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

