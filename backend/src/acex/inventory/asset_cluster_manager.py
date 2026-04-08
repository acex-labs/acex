

from acex.models.asset import AssetClusterCreate, AssetClusterUpdate, AssetCluster, AssetClusterLink, AssetClusterResponse, AssetClusterAssetResponse
from fastapi import HTTPException

class AssetClusterManager:

    def __init__(self, db_manager):
        self.db = db_manager

    def create_cluster(self, payload: AssetClusterCreate) -> AssetCluster:
        session = next(self.db.get_session())
        try:
            cluster = AssetCluster.model_validate(payload)
            session.add(cluster)
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
                    cluster_index=order_map.get(asset.id)
                )
                for asset in cluster.assets
            ]
            assets.sort(key=lambda a: (a.cluster_index if a.cluster_index is not None else 0))

            return AssetClusterResponse(
                id=cluster.id,
                name=cluster.name,
                ned_id=cluster.ned_id,
                assets=assets
            )
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
                session.exec(
                    AssetClusterLink.__table__.delete().where(AssetClusterLink.cluster_id == id)
                )
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