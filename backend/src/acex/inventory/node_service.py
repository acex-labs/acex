import inspect
from acex.models import Node, NodeResponse
from acex.plugins.neds.manager.ned_manager import NEDManager
from acex.models.asset import Asset

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
        if node.get("asset_ref_type") == "assetcluster":
            asset = self.inventory.asset_cluster_manager.get_cluster(node["asset_ref_id"])
        else:
            asset = self.inventory.assets.get(node["asset_ref_id"])
        if isinstance(asset, Asset):
            node["asset"] = asset.model_dump()
        else:
            node["asset"] = asset
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

        asset = None
        if getattr(ni, "asset_ref_type", "asset") == "assetcluster":
            asset = self.inventory.assetclusters.get(ni.asset_ref_id)
        else:
            asset = self.inventory.assets.get(ni.asset_ref_id)

        print(f"fetch ned: {asset.ned_id}")
        ned_manager = NEDManager()
        ned = ned_manager.get_driver_instance(asset.ned_id)

        if ned is None:
            return "error: NED not found"
        try:
            config = ned.render(logical_node=ln, asset=asset)
        except Exception as e:
            print("ERROR: Failed to render configuration.")
            print(e)
            # TODO: Printa hela tb
            config = ""
        return config
    
    async def create(self, logical_node: Node):
        result = await self._call_method(self.adapter.create, logical_node)
        return result
    
    async def get(self, id: str):
        result = await self._call_method(self.adapter.get, id)
        result = await self._enrich_data(result)
        return result

    async def query(self):
        result = await self._call_method(self.adapter.query)
        return result

    async def update(self, id: str, logical_node: Node):
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
