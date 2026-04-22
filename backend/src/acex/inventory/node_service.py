import inspect
from datetime import datetime
from acex.models import Node, NodeResponse, NodeListResponse, PaginatedResponse
from acex.models.node import NodeStatus
from acex.plugins.neds.manager.ned_manager import NEDManager
from acex.models.asset import Asset
from typing import List, Optional

class NodeService:
    """Service layer för Node business logik."""

    def __init__(self, adapter, inventory):
        self.adapter = adapter
        self.inventory = inventory

    async def _call_method(self, method, *args, **kwargs):
        """Helper för att hantera både sync och async metoder."""
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)

    async def _enrich_data(self, node):
        """När en specific node hämtas vill vi, 
        berika responsen med datat från refererade objekt."""

        if node is None:
            return None

        node = node.model_dump()
        asset = None
        if node.get("asset_ref_type") == "asset_cluster":
            asset = self.inventory.asset_cluster_manager.get_cluster(node["asset_ref_id"])
        else:
            asset = await self.inventory.assets.get(node["asset_ref_id"])
        node["asset"] = asset.model_dump() if hasattr(asset, 'model_dump') else asset
        ln = await self.inventory.logical_nodes.get(node["logical_node_id"])
        if ln is not None:
            node["logical_node"] = ln.model_dump()

        return NodeResponse(**node)

    async def get_rendered_config(self, id: str):
        """
        Renderar konfigurationen för en nod instans.
        """
        ni = await self.get(id)
        ln = await self.inventory.logical_nodes.get(ni.logical_node_id)
        composed_config = ln.configuration

        asset = None
        if getattr(ni, "asset_ref_type", "asset") == "asset_cluster":
            asset = self.inventory.asset_cluster_manager.get_cluster(ni.asset_ref_id)
        else:
            asset = await self.inventory.assets.get(ni.asset_ref_id)

        ned_manager = NEDManager()
        ned = ned_manager.get_driver_instance(asset.ned_id)

        if ned is None:
            return "error: NED not found"
        try:
            config = ned.render(configuration=composed_config, asset=asset)
        except Exception as e:
            # Skriver ut felmeddelandet
            print("Fel:", e)
            # Skriver ut hela tracebacken
            import traceback
            traceback.print_exc()
            # Todo, printa ut mer info från vilken render och vad som pajjat
            # Fel: render trasig
            # Render XYZ trasig
            # Node ID X triggade fel
            # På den här filen kommer tracen
            # Här kommer traceback mannen:
            # tracen
            
            config = ""
        return config
    
    async def create(self, logical_node: Node):
        result = await self._call_method(self.adapter.create, logical_node)
        return result
    
    async def get(self, id: str) -> NodeResponse:
        result = await self._call_method(self.adapter.get, id)
        result = await self._enrich_data(result)
        return result

    async def query(
        self,
        site: str = None,
        hostname: str = None,
        logical_node_id: int = None,
        asset_ref_id: int = None,
        status: Optional[NodeStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[NodeListResponse]:

        query_filters = {
            k: v for k, v in {
                "logical_node.site": site,
                "logical_node.hostname": hostname,
                "logical_node_id": logical_node_id,
                "asset_ref_id": asset_ref_id,
                "status": status,
            }.items() if v is not None
        }
        result = await self._call_method(self.adapter.query, filters=query_filters, limit=limit, offset=offset)

        # Bulk-fetch unique assets and clusters to avoid N+1
        asset_ids = {n.asset_ref_id for n in result["items"] if getattr(n, "asset_ref_type", "asset") == "asset"}
        cluster_ids = {n.asset_ref_id for n in result["items"] if getattr(n, "asset_ref_type", None) == "asset_cluster"}

        assets_by_id = {}
        for aid in asset_ids:
            asset = await self._call_method(self.inventory.assets.adapter.get, aid)
            if asset:
                assets_by_id[aid] = asset

        clusters_by_id = {}
        for cid in cluster_ids:
            cluster = self.inventory.asset_cluster_manager.get_cluster(cid)
            if cluster:
                clusters_by_id[cid] = cluster

        items = []
        for node in result["items"]:
            if getattr(node, "asset_ref_type", "asset") == "asset_cluster":
                cluster = clusters_by_id.get(node.asset_ref_id)
                vendor = None
                os_val = None
                ned_id = cluster.ned_id if cluster else None
            else:
                asset = assets_by_id.get(node.asset_ref_id)
                vendor = asset.vendor if asset else None
                os_val = asset.os if asset else None
                ned_id = asset.ned_id if asset else None
            items.append(NodeListResponse(
                **node.model_dump(),
                hostname=node.logical_node.hostname if node.logical_node else None,
                site=node.logical_node.site if node.logical_node else None,
                vendor=vendor,
                os=os_val,
                ned_id=ned_id,
            ))

        return PaginatedResponse(items=items, total=result["total"], limit=limit, offset=offset)

    async def update(self, id: str, logical_node: Node):
        logical_node.updated_at = datetime.utcnow()
        result = await self._call_method(self.adapter.update, id, logical_node)
        return result
    
    async def delete(self, id: str):
        result = await self._call_method(self.adapter.delete, id)
        return result
    
    @property
    def capabilities(self):
        return self.adapter.capabilities

    def path(self, capability):
        return self.adapter.path(capability)
    
    def http_verb(self, capability):
        return self.adapter.http_verb(capability)
