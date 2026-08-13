from acex_devkit.models.management_connection import (
    ManagementConnectionCreate,
    ManagementConnectionResponse,
    ManagementConnectionUpdate,
)

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)


class ManagementConnections(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/management_connections"
    response_model = ManagementConnectionResponse
    list_model = ManagementConnectionResponse
    create_model = ManagementConnectionCreate
    update_model = ManagementConnectionUpdate
