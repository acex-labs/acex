from acex_devkit.models.logical_node import (
    LogicalNodeConfigResponse,
    LogicalNodeCreate,
    LogicalNodeListResponse,
    LogicalNodeResponse,
    LogicalNodeUpdate,
)

from acex_client.resources.base import (
    ActionMixin,
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
    action,
)


class LogicalNodes(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin, ActionMixin):
    path = "/inventory/logical_nodes"
    response_model = LogicalNodeResponse
    list_model = LogicalNodeListResponse
    create_model = LogicalNodeCreate
    update_model = LogicalNodeUpdate

    @action("GET", "{id}/configuration")
    def configuration(self, id: int) -> LogicalNodeConfigResponse: ...
