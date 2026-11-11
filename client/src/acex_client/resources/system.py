from acex_devkit.models.auth_config import AuthConfig

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class SystemNamespace(Resource, ActionMixin):
    """System endpoints — `/auth/config`."""

    path = ""
    response_model = None  # type: ignore
    list_model = None  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "/auth/config")
    def auth_config(self) -> AuthConfig: ...
