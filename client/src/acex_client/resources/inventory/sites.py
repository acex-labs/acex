from acex_devkit.models.site import SiteCreate, SiteResponse, SiteUpdate

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)


class Sites(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/sites"
    response_model = SiteResponse
    list_model = SiteResponse
    create_model = SiteCreate
    update_model = SiteUpdate
