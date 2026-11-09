"""Tests for @action decorator on Resource subclasses via respx."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.base import (
    ActionMixin,
    GetMixin,
    ListMixin,
    Resource,
    _serialize_body,
    action,
    stream,
)
from acex_client.resources.cve import Cves
from acex_devkit.models.agent_manifest import AckResult, CollectionAgentManifest
from acex_devkit.models.collection_agent import (
    CollectionAgentAck,
    CollectionAgentResponse,
)
from acex_devkit.models.cve import CveApiKeyUpdate, CveCreate, CveDiscoverData, CveResponse
from httpx import Response
from pydantic import BaseModel


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


def test_shared_action_serializer_preserves_python_mode():
    class Payload(BaseModel):
        timestamp: datetime
        optional: str | None = None

    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    payload = Payload(timestamp=timestamp)

    assert _serialize_body(payload) == {"timestamp": timestamp}
    assert _serialize_body([payload]) == [{"timestamp": timestamp}]


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
def test_cve_discovery_and_bulk_create_actions(rest):
    discover = respx.post("http://test/api/v1/cves/discover").mock(
        return_value=Response(
            202,
            json={
                "id": 18,
                "type": "acex.cve.discover",
                "data": {"vendor": "Cisco", "start": None, "end": None},
                "state": "queued",
                "created_by": "alice",
                "created_at": "2026-01-01T00:00:00Z",
            },
        )
    )
    bulk_create = respx.post("http://test/api/v1/cves/bulk").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 3,
                    "cve_id": "CVE-2026-1234",
                    "raw": {"id": "CVE-2026-1234"},
                    "published": None,
                    "last_modified": None,
                    "description": None,
                    "cvss_score": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": None,
                }
            ],
        )
    )
    cves = Cves(rest)

    published = datetime(2026, 1, 1, tzinfo=UTC)
    last_modified = datetime(2026, 1, 2, tzinfo=UTC)
    job = cves.discover(payload=CveDiscoverData(vendor="Cisco", start=published, end=last_modified))
    created = cves.bulk_create(
        payload=[
            CveCreate(
                cve_id="CVE-2026-1234",
                published=published,
                last_modified=last_modified,
                raw={"id": "CVE-2026-1234"},
            )
        ]
    )

    assert discover.called
    assert json.loads(discover.calls.last.request.content) == {
        "vendor": "Cisco",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
    }
    assert job.type == "acex.cve.discover"
    assert bulk_create.called
    assert json.loads(bulk_create.calls.last.request.content) == [
        {
            "cve_id": "CVE-2026-1234",
            "published": "2026-01-01T00:00:00+00:00",
            "last_modified": "2026-01-02T00:00:00+00:00",
            "raw": {"id": "CVE-2026-1234"},
        }
    ]
    assert len(created) == 1
    assert isinstance(created[0], CveResponse)
    assert created[0].cve_id == "CVE-2026-1234"


@respx.mock
def test_cve_query_returns_a_paginated_result(rest):
    route = respx.get("http://test/api/v1/cves").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": 3,
                        "cve_id": "CVE-2026-1234",
                        "raw": {"id": "CVE-2026-1234"},
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "total": 7,
                "limit": 1,
                "offset": 2,
            },
        )
    )

    page = Cves(rest).query(limit=1, offset=2)

    assert dict(route.calls.last.request.url.params) == {"limit": "1", "offset": "2"}
    assert (page.total, page.limit, page.offset) == (7, 1, 2)
    assert isinstance(page.items[0], CveResponse)


@respx.mock
@pytest.mark.parametrize("method", ["create", "update", "bulk_create"])
def test_cve_mutations_serialize_datetime_fields(rest, method):
    published = datetime(2026, 1, 1, tzinfo=UTC)
    payload = CveCreate(
        cve_id="CVE-2026-1234",
        published=published,
        last_modified=published,
        raw={"id": "CVE-2026-1234"},
    )
    body = {
        "cve_id": "CVE-2026-1234",
        "published": "2026-01-01T00:00:00+00:00",
        "last_modified": "2026-01-01T00:00:00+00:00",
        "raw": {"id": "CVE-2026-1234"},
    }
    response = {**body, "id": 3, "created_at": "2026-01-01T00:00:00Z"}
    cves = Cves(rest)
    if method == "bulk_create":
        route = respx.post("http://test/api/v1/cves/bulk").mock(return_value=Response(200, json=[response]))
        result = cves.bulk_create(payload=[payload])[0]
        expected_body = [body]
    elif method == "update":
        route = respx.patch("http://test/api/v1/cves/3").mock(return_value=Response(200, json=response))
        result = cves.update(cve_id=3, payload=payload)
        expected_body = body
    else:
        route = respx.post("http://test/api/v1/cves").mock(return_value=Response(200, json=response))
        result = cves.create(payload=payload)
        expected_body = body

    assert json.loads(route.calls.last.request.content) == expected_body
    assert result.published == published
    assert result.last_modified == published


@respx.mock
@pytest.mark.parametrize("key", ["test-nvd-key", None])
def test_cve_api_key_action_returns_a_json_string_or_none(rest, key):
    route = respx.get("http://test/api/v1/cves/api_key").mock(
        return_value=Response(200, content="null" if key is None else '"test-nvd-key"')
    )
    cves = Cves(rest)
    assert cves.api_key.rest is rest
    assert cves.api_key.get() == key
    assert route.called


@respx.mock
def test_cve_api_key_save_and_delete_actions(rest):
    save = respx.put("http://test/api/v1/cves/api_key").mock(return_value=Response(204))
    delete = respx.delete("http://test/api/v1/cves/api_key").mock(return_value=Response(204))
    cves = Cves(rest)

    assert cves.api_key.update(payload=CveApiKeyUpdate(api_key="test-nvd-key")) is None
    assert save.calls.last.request.content == b'{"api_key":"test-nvd-key"}'
    assert cves.api_key.delete() is None
    assert delete.called


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
