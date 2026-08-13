from acex_devkit.models.region import RegionCreate, RegionResponse, RegionUpdate

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)


class Regions(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/regions"
    response_model = RegionResponse
    list_model = RegionResponse
    create_model = RegionCreate
    update_model = RegionUpdate
