from acex_devkit.models.credential import (
    CredentialCreate,
    CredentialResponse,
    CredentialSecret,
    CredentialUpdate,
    NodeCredentialCreate,
    NodeCredentialResponse,
)

from acex_client.resources.base import (
    ActionMixin,
    BoundCreateMixin,
    BoundDeleteMixin,
    BoundListMixin,
    BoundResource,
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
    action,
)


class Credentials(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin, ActionMixin):
    path = "/inventory/credentials"
    response_model = CredentialResponse
    list_model = CredentialResponse
    create_model = CredentialCreate
    update_model = CredentialUpdate

    @action("GET", "{id}/secret")
    def secret(self, id: int) -> CredentialSecret: ...


class NodeCredentials(BoundResource, BoundListMixin, BoundCreateMixin, BoundDeleteMixin):
    """Credentials assigned to a node — `/inventory/nodes/{node_id}/credentials`."""

    path_template = "/inventory/nodes/{parent_id}/credentials"
    response_model = NodeCredentialResponse
    list_model = NodeCredentialResponse
    create_model = NodeCredentialCreate


class SiteCredentials(BoundResource, BoundListMixin, BoundCreateMixin, BoundDeleteMixin):
    """Credentials assigned to a site — `/inventory/sites/{site_name}/credentials`."""

    path_template = "/inventory/sites/{parent_id}/credentials"
    response_model = NodeCredentialResponse
    list_model = NodeCredentialResponse
    create_model = NodeCredentialCreate
