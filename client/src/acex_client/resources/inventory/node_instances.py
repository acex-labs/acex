import base64
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


def _b64_encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _b64_decode(text: str) -> str:
    return base64.b64decode(text).decode("utf-8", errors="replace")


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

    def upload_observed(self, id: int, payload: DeviceConfigUpload) -> Any:
        encoded = DeviceConfigUpload(content=_b64_encode(payload.content))
        body = encoded.model_dump(exclude_none=True)
        return self.rest.request("POST", f"{self.path}/{id}/configuration/observed", json=body)

    @action("GET", "{id}/configuration/observed")
    def list_observed(self, id: int) -> list[ConfigSnapshotListItem]: ...

    def get_latest_observed(self, id: int, output: ConfigOutput = ConfigOutput.RENDERED) -> ConfigSnapshotDetail:
        params = {"output": str(output)}
        data = self.rest.request("GET", f"{self.path}/{id}/configuration/observed/latest", params=params)
        return self._decode_snapshot(data)

    def get_observed(
        self, id: int, config_id: int, output: ConfigOutput = ConfigOutput.RENDERED
    ) -> ConfigSnapshotDetail:
        params = {"output": str(output)}
        data = self.rest.request("GET", f"{self.path}/{id}/configuration/observed/{config_id}", params=params)
        return self._decode_snapshot(data)

    @action("GET", "{id}/configuration/observed/diff")
    def diff_observed(self, id: int, a: int, b: int) -> ConfigDiffResult: ...

    @action("GET", "{id}/configuration/intent_diff")
    def intent_diff(self, id: int) -> Diff: ...

    @staticmethod
    def _decode_snapshot(data: Any) -> ConfigSnapshotDetail | None:
        if data is None:
            return None
        content = data.get("content") if isinstance(data, dict) else None
        if isinstance(content, str):
            try:
                data["content"] = _b64_decode(content)
            except Exception:
                pass
        return ConfigSnapshotDetail.model_validate(data)
