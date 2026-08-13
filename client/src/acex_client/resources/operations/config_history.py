from acex_devkit.models.config_snapshot import ConfigChangeListResult

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class ConfigHistory(Resource, ActionMixin):
    """Configuration change history — `/operations/configuration/changes`."""

    path = "/operations/configuration"
    response_model = ConfigChangeListResult
    list_model = ConfigChangeListResult
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "changes")
    def list_changes(
        self,
        node_instance_id: int | None = None,
        site: str | None = None,
        hostname: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ConfigChangeListResult: ...
