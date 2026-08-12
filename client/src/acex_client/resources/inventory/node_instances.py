from typing import Any

from acex_devkit.configdiffer.diff import Diff
from acex_devkit.models.config_snapshot import (
    ConfigDiffResult,
    ConfigOutput,
    ConfigSnapshotDetail,
    ConfigSnapshotListItem,
    DeviceConfigUpload,
)
from acex_devkit.models.node_response import (
    NodeCreate,
    NodeListItem,
    NodeResponse,
    NodeUpdate,
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


class NodeInstances(
    Resource,
    GetMixin,
    ListMixin,
    CreateMixin,
    UpdateMixin,
    DeleteMixin,
    ActionMixin,
):
    path = "/inventory/node_instances"
    response_model = NodeResponse
    list_model = NodeListItem
    create_model = NodeCreate
    update_model = NodeUpdate

    @action("GET", "{id}/configuration/desired")
    def configuration_desired(self, id: int) -> str: ...

    @action("POST", "{id}/configuration/observed/")
    def upload_observed(self, id: int, payload: DeviceConfigUpload) -> Any: ...

    @action("GET", "{id}/configuration/observed/")
    def list_observed(self, id: int) -> list[ConfigSnapshotListItem]: ...

    @action("GET", "{id}/configuration/observed/latest")
    def get_latest_observed(self, id: int, output: ConfigOutput = ConfigOutput.RENDERED) -> ConfigSnapshotDetail: ...

    @action("GET", "{id}/configuration/observed/{config_id}")
    def get_observed(
        self, id: int, config_id: int, output: ConfigOutput = ConfigOutput.RENDERED
    ) -> ConfigSnapshotDetail: ...

    @action("GET", "{id}/configuration/observed/diff")
    def diff_observed(self, id: int, a: int, b: int) -> ConfigDiffResult: ...

    @action("GET", "{id}/configuration/intent_diff")
    def intent_diff(self, id: int) -> Diff: ...
