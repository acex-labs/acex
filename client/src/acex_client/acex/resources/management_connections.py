from acex_devkit.models.management_connection import ManagementConnectionResponse
from .resource_base import Resource, GetMixin, ListMixin, CreateMixin, DeleteMixin


class ManagementConnections(Resource, GetMixin, ListMixin, CreateMixin, DeleteMixin):

    ENDPOINT = "/inventory/management_connections/"
    RESPONSE_MODEL_SINGLE = ManagementConnectionResponse
    RESPONSE_MODEL_LIST = ManagementConnectionResponse