"""Tests for @action decorator on Resource subclasses via respx."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.base import (
    ActionMixin,
    GetMixin,
    ListMixin,
    Resource,
    action,
    stream,
)
from acex_devkit.models.agent_manifest import AckResult, CollectionAgentManifest
from acex_devkit.models.collection_agent import (
    CollectionAgentAck,
    CollectionAgentResponse,
)
from httpx import Response


class CollectionAgents(Resource, GetMixin, ListMixin, ActionMixin):
    path = "/inventory/collection_agents"
    response_model = CollectionAgentResponse
    list_model = CollectionAgentResponse
    create_model = CollectionAgentResponse
    update_model = CollectionAgentResponse

    @action("POST", "{id}/ack")
    def ack(self, id: int, payload: CollectionAgentAck) -> AckResult: ...

    @action("GET", "{id}/manifest")
    def manifest(self, id: int) -> CollectionAgentManifest: ...


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@respx.mock
def test_action_with_body(rest):
    route = respx.post("http://test/api/v1/inventory/collection_agents/1/ack").mock(
        return_value=Response(200, json={"id": 1, "acked_revision": 5, "acked_at": "2024-01-01T00:00:00"})
    )
    result = CollectionAgents(rest).ack(id=1, payload=CollectionAgentAck(config_revision=5))
    assert route.called
    assert result.id == 1
    assert result.acked_revision == 5


@respx.mock
def test_action_with_path_substitution(rest):
    respx.get("http://test/api/v1/inventory/collection_agents/2/manifest").mock(
        return_value=Response(
            200,
            json={
                "agent_id": 2,
                "name": "agent-2",
                "config_revision": 3,
                "interval_seconds": 60,
                "enabled": True,
                "targets": [],
            },
        )
    )
    result = CollectionAgents(rest).manifest(id=2)
    assert result.agent_id == 2
    assert result.name == "agent-2"
    assert result.targets == []


@respx.mock
def test_action_via_live_instance(rest):
    # Bind the action to a fetched resource and verify it calls with parent id.
    respx.get("http://test/api/v1/inventory/collection_agents/3").mock(
        return_value=Response(
            200,
            json={
                "id": 3,
                "name": "agent-3",
                "config_revision": 1,
                "acked_revision": 0,
            },
        )
    )
    route = respx.post("http://test/api/v1/inventory/collection_agents/3/ack").mock(
        return_value=Response(200, json={"id": 3, "acked_revision": 2, "acked_at": "2024-01-01"})
    )
    agent = CollectionAgents(rest).get(3)
    result = agent.ack(payload=CollectionAgentAck(config_revision=2))
    assert route.called
    assert result.acked_revision == 2


@respx.mock
def test_stream_yields_data_lines(rest):
    body = b"event: token\ndata: Hello\n\nevent: token\ndata:  world\n\n"
    respx.post("http://test/api/v1/ai_ops/ai/ask/").mock(
        return_value=Response(200, content=body, headers={"content-type": "text/event-stream"})
    )

    class Ai(Resource):
        path = "/ai_ops/ai"
        response_model = None  # type: ignore

        @stream("POST", "ask/")
        def ask(self, question: str) -> Iterator[str]: ...

    chunks = list(Ai(rest).ask(question="hello"))
    assert chunks == ["Hello", "world"]
