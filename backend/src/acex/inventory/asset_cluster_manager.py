from acex.models.asset import (
    AssetCluster,
    AssetClusterAssetResponse,
    AssetClusterCreate,
    AssetClusterLink,
    AssetClusterResponse,
    AssetClusterUpdate,
)
from fastapi import HTTPException


class AssetClusterManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def _check_assets_available(self, session, asset_ids: list[int], exclude_cluster_id: int | None = None) -> None:
        for asset_id in asset_ids:
            link = (
                session.query(AssetClusterLink)
                .filter(AssetClusterLink.asset_id == asset_id)
                .first()
            )
            if link and link.cluster_id != exclude_cluster_id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Asset {asset_id} is already assigned to cluster {link.cluster_id}",
                )

    def create_cluster(self, payload: AssetClusterCreate) -> AssetCluster:
        session = next(self.db.get_session())
        try:
            self._check_assets_available(session, payload.asset_ids)
            cluster = AssetCluster.model_validate(payload)
            session.add(cluster)
            session.commit()
            session.refresh(cluster)
            for order, asset_id in enumerate(payload.asset_ids):
                link = AssetClusterLink(asset_id=asset_id, cluster_id=cluster.id, order=order)
                session.add(link)
            if payload.asset_ids:
                session.commit()
                session.refresh(cluster)
            return cluster
        finally:
            session.close()

    def list_clusters(self) -> list[AssetCluster]:
        session = next(self.db.get_session())
        try:
            return session.query(AssetCluster).all()
        finally:
            session.close()

    def get_cluster(self, id: int) -> AssetClusterResponse:
        session = next(self.db.get_session())
        try:
            cluster = session.get(AssetCluster, id)
            if not cluster:
                raise HTTPException(status_code=404, detail="AssetCluster not found")

            links = session.query(AssetClusterLink).filter(AssetClusterLink.cluster_id == id).all()
            order_map = {link.asset_id: link.order for link in links}

            assets = [
                AssetClusterAssetResponse(
                    id=asset.id,
                    vendor=asset.vendor,
                    serial_number=asset.serial_number,
                    os=asset.os,
                    os_version=asset.os_version,
                    hardware_model=asset.hardware_model,
                    ned_id=asset.ned_id,
                    cluster_index=order_map.get(asset.id),
                )
                for asset in cluster.assets
            ]
            assets.sort(key=lambda a: a.cluster_index if a.cluster_index is not None else 0)

            return AssetClusterResponse(id=cluster.id, name=cluster.name, ned_id=cluster.ned_id, assets=assets)
        finally:
            session.close()

    def update_cluster(self, id: int, payload: AssetClusterUpdate) -> AssetCluster:
        session = next(self.db.get_session())
        try:
            cluster = session.get(AssetCluster, id)
            if not cluster:
                raise HTTPException(status_code=404, detail="AssetCluster not found")

            if payload.name is not None:
                cluster.name = payload.name
            if payload.ned_id is not None:
                cluster.ned_id = payload.ned_id

            if payload.asset_ids is not None:
                self._check_assets_available(session, payload.asset_ids, exclude_cluster_id=id)
                session.exec(AssetClusterLink.__table__.delete().where(AssetClusterLink.cluster_id == id))
                for order, asset_id in enumerate(payload.asset_ids):
                    link = AssetClusterLink(asset_id=asset_id, cluster_id=id, order=order)
                    session.add(link)

            session.commit()
            session.refresh(cluster)
            return cluster
        finally:
            session.close()

    def delete_cluster(self, id: int) -> None:
        session = next(self.db.get_session())
        try:
            cluster = session.get(AssetCluster, id)
            if not cluster:
                raise HTTPException(status_code=404, detail="AssetCluster not found")
            session.delete(cluster)
            session.commit()
        finally:
            session.close()
