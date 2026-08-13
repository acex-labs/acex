from acex_devkit.models.agent_manifest import AckResult
from acex_devkit.models.telemetry_agent import (
    OutputDestinationCreate,
    OutputDestinationResponse,
    OutputDestinationUpdate,
    TelemetryAgentAck,
    TelemetryAgentCreate,
    TelemetryAgentMatchRuleCreate,
    TelemetryAgentMatchRuleResponse,
    TelemetryAgentResponse,
    TelemetryAgentUpdate,
)

from acex_client.resources.base import (
    ActionMixin,
    BoundCreateMixin,
    BoundDeleteMixin,
    BoundListMixin,
    BoundResource,
    BoundUpdateMixin,
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    PaginatedResult,
    Resource,
    UpdateMixin,
    action,
    sub_resource,
)


def _paginate(items, data, limit, offset) -> PaginatedResult:
    """Build a PaginatedResult from a `{items, total, limit, offset}` dict response."""
    return PaginatedResult(
        items,
        data.get("total", len(items)),
        data.get("limit", limit),
        data.get("offset", offset),
    )


class ObservabilityAgentRules(BoundResource, BoundListMixin, BoundCreateMixin, BoundDeleteMixin):
    """Nested CRUD for `POST/GET/DELETE /observability/agents/{id}/rules`."""

    path_template = "/observability/agents/{parent_id}/rules/{rule_id}"
    response_model = TelemetryAgentMatchRuleResponse
    list_model = TelemetryAgentMatchRuleResponse
    create_model = TelemetryAgentMatchRuleCreate

    def _collection_path(self) -> str:
        return f"/observability/agents/{self.parent_id}/rules"

    def query(self, limit: int = 100, offset: int = 0, **filters):
        from acex_client.resources.base import PaginatedResult

        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.request("GET", self._collection_path(), params=params)
        if isinstance(data, dict) and "items" in data:
            items = [self.list_model(**item) for item in data["items"]]
            return _paginate(items, data, limit, offset)
        if isinstance(data, list):
            items = [self.list_model(**item) for item in data]
            return PaginatedResult(items, len(items), len(items), 0)
        return PaginatedResult([], 0, limit, offset)

    def create(self, **body):
        validated = self.create_model(**body)
        payload = validated.model_dump(exclude_none=True)
        data = self.rest.request("POST", self._collection_path(), json=payload)
        return self._make_live(self.response_model(**data))


class ObservabilityAgentNodes(BoundResource, BoundCreateMixin, BoundDeleteMixin):
    """Node membership: `POST/DELETE /observability/agents/{id}/nodes/{node_id}`.

    No list or get; membership is reflected on the agent itself.
    """

    path_template = "/observability/agents/{parent_id}/nodes/{node_id}"
    response_model = None  # type: ignore
    list_model = None  # type: ignore
    create_model = None  # type: ignore


class ObservabilityAgentOutputs(BoundResource, BoundListMixin, BoundCreateMixin, BoundUpdateMixin, BoundDeleteMixin):
    """Nested CRUD for `POST/GET/PATCH/DELETE /observability/agents/{id}/outputs[/...]`."""

    path_template = "/observability/agents/{parent_id}/outputs/{output_id}"
    response_model = OutputDestinationResponse
    list_model = OutputDestinationResponse
    create_model = OutputDestinationCreate
    update_model = OutputDestinationUpdate

    def _collection_path(self) -> str:
        return f"/observability/agents/{self.parent_id}/outputs"

    def query(self, limit: int = 100, offset: int = 0, **filters):
        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.request("GET", self._collection_path(), params=params)
        if isinstance(data, dict) and "items" in data:
            items = [self.list_model(**item) for item in data["items"]]
            return _paginate(items, data, limit, offset)
        if isinstance(data, list):
            items = [self.list_model(**item) for item in data]
            return PaginatedResult(items, len(items), len(items), 0)
        return PaginatedResult([], 0, limit, offset)

    def create(self, **body):
        validated = self.create_model(**body)
        payload = validated.model_dump(exclude_none=True)
        data = self.rest.request("POST", self._collection_path(), json=payload)
        return self._make_live(self.response_model(**data))


class ObservabilityAgents(
    Resource,
    GetMixin,
    ListMixin,
    CreateMixin,
    UpdateMixin,
    DeleteMixin,
    ActionMixin,
):
    path = "/observability/agents"
    response_model = TelemetryAgentResponse
    list_model = TelemetryAgentResponse
    create_model = TelemetryAgentCreate
    update_model = TelemetryAgentUpdate

    @sub_resource("rules")
    def rules(self, parent_id: int) -> ObservabilityAgentRules: ...

    @sub_resource("nodes")
    def nodes(self, parent_id: int) -> ObservabilityAgentNodes: ...

    @sub_resource("outputs")
    def outputs(self, parent_id: int) -> ObservabilityAgentOutputs: ...

    @action("POST", "{id}/nodes/{node_id}")
    def add_node(self, id: int, node_id: int) -> None: ...

    @action("DELETE", "{id}/nodes/{node_id}")
    def remove_node(self, id: int, node_id: int) -> None: ...

    @action("POST", "{id}/ack")
    def ack(self, id: int, payload: TelemetryAgentAck) -> AckResult: ...

    @action("GET", "{id}/config")
    def config(self, id: int) -> str: ...
