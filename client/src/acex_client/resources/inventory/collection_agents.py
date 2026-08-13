from acex_devkit.models.agent_manifest import AckResult, CollectionAgentManifest
from acex_devkit.models.collection_agent import (
    CollectionAgentAck,
    CollectionAgentCreate,
    CollectionAgentMatchRuleCreate,
    CollectionAgentMatchRuleResponse,
    CollectionAgentResponse,
    CollectionAgentUpdate,
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
    sub_resource,
)


class CollectionAgentRules(BoundResource, BoundListMixin, BoundCreateMixin, BoundDeleteMixin):
    """Nested CRUD for `POST/GET/DELETE /collection_agents/{id}/rules`.

    - List/create use the collection path `/collection_agents/{id}/rules`.
    - Delete targets the specific-rule path
      `/collection_agents/{id}/rules/{rule_id}` via `delete(rule_id=...)`.
      `BoundDeleteMixin.delete` formats `path_template` with all kwargs +
      parent_id, so we just include `{rule_id}` here.
    """

    path_template = "/inventory/collection_agents/{parent_id}/rules/{rule_id}"

    # Override list/create to use the collection path (without rule_id).
    def _collection_path(self) -> str:
        return f"/inventory/collection_agents/{self.parent_id}/rules"

    def query(self, limit: int = 100, offset: int = 0, **filters):
        params = {k: v for k, v in filters.items() if v is not None}
        params["limit"] = limit
        params["offset"] = offset
        data = self.rest.request("GET", self._collection_path(), params=params)
        from acex_client.resources.base import PaginatedResult, _paginate

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

    response_model = CollectionAgentMatchRuleResponse
    list_model = CollectionAgentMatchRuleResponse
    create_model = CollectionAgentMatchRuleCreate


class CollectionAgents(
    Resource,
    GetMixin,
    ListMixin,
    CreateMixin,
    UpdateMixin,
    DeleteMixin,
    ActionMixin,
):
    path = "/inventory/collection_agents"
    response_model = CollectionAgentResponse
    list_model = CollectionAgentResponse
    create_model = CollectionAgentCreate
    update_model = CollectionAgentUpdate

    @sub_resource("rules")
    def rules(self, parent_id: int) -> CollectionAgentRules: ...

    # Node membership is exposed via plain @action because the path has two
    # variables ({id} + {node_id}). BoundResource fits the single-parent case
    # (rules above); multi-segment membership paths are simpler as actions.
    @action("POST", "{id}/nodes/{node_id}")
    def add_node(self, id: int, node_id: int) -> None: ...

    @action("DELETE", "{id}/nodes/{node_id}")
    def remove_node(self, id: int, node_id: int) -> None: ...

    @action("POST", "{id}/ack")
    def ack(self, id: int, payload: CollectionAgentAck) -> AckResult: ...

    @action("GET", "{id}/manifest")
    def manifest(self, id: int) -> CollectionAgentManifest: ...
