from acex_devkit.models.asset import (
    AssetClusterCreate,
    AssetClusterResponse,
    AssetClusterUpdate,
)

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)


class AssetClusters(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/asset_clusters"
    response_model = AssetClusterResponse
    list_model = AssetClusterResponse
    create_model = AssetClusterCreate
    update_model = AssetClusterUpdate
