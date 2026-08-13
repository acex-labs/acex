from acex_devkit.models.asset import (
    AssetCreate,
    AssetResponse,
    AssetUpdate,
)

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)


class Assets(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/assets"
    response_model = AssetResponse
    list_model = AssetResponse
    create_model = AssetCreate
    update_model = AssetUpdate
