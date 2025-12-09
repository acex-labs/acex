

from acex.models.asset import AssetClusterCreate, AssetCluster, AssetClusterLink
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

    def get_cluster(self, id: int) -> dict:
        session = next(self.db.get_session())
        try:
            cluster = session.get(AssetCluster, id)
            if not cluster:
                raise HTTPException(status_code=404, detail="AssetCluster not found")
            # assets laddas automatiskt via relationship, men vi serialiserar till dict
            return {
                "id": cluster.id,
                "name": cluster.name,
                "assets": [
                    {
                        "id": asset.id,
                        "vendor": asset.vendor,
                        "serial_number": asset.serial_number,
                        "os": asset.os,
                        "os_version": asset.os_version,
                        "hardware_model": asset.hardware_model,
                        "ned_id": asset.ned_id
                    }
                    for asset in cluster.assets
                ]
            }
        finally:
            session.close()

    def update_cluster_assets(self, cluster_id: int, asset_ids: list[int]) -> AssetCluster:
        session = next(self.db.get_session())
        try:
            cluster = session.get(AssetCluster, cluster_id)
            if not cluster:
                raise HTTPException(status_code=404, detail="AssetCluster not found")

            # Ta bort gamla länkar
            session.exec(
                AssetClusterLink.__table__.delete().where(AssetClusterLink.cluster_id == cluster_id)
            )

            # Lägg till nya länkar
            for order, asset_id in enumerate(asset_ids):
                link = AssetClusterLink(asset_id=asset_id, cluster_id=cluster_id, order=order)
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