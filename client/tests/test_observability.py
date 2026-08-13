"""Tests for observability resources via respx mocks."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.observability import ObservabilityNamespace
from httpx import Response


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@pytest.fixture
def observability(rest):
    return ObservabilityNamespace(rest)


@respx.mock
def test_agent_crud(observability):
    respx.post("http://test/api/v1/observability/agents").mock(
        return_value=Response(
            201,
            json={
                "id": 1,
                "name": "agent-1",
                "description": "first",
                "config_revision": 0,
                "acked_revision": 0,
                "capabilities": ["icmp"],
                "nodes": [],
                "rules": [],
                "resolved_nodes": [],
                "outputs": [],
            },
        )
    )
    respx.get("http://test/api/v1/observability/agents/1").mock(
        return_value=Response(
            200,
            json={
                "id": 1,
                "name": "agent-1",
                "description": "first",
            },
        )
    )
    agent = observability.agents.create(name="agent-1", description="first", capabilities=["icmp"])
    assert agent.id == 1
    assert "icmp" in agent.capabilities

    fetched = observability.agents.get(1)
    assert fetched.name == "agent-1"


@respx.mock
def test_agent_config_action(observability):
    respx.get("http://test/api/v1/observability/agents/2/config").mock(
        return_value=Response(200, text="# telegraf config\n[[inputs.ping]]")
    )
    cfg = observability.agents.config(id=2)
    assert "telegraf" in cfg
    assert "[[inputs.ping]]" in cfg


@respx.mock
def test_agent_ack_action(observability):
    respx.post("http://test/api/v1/observability/agents/3/ack").mock(
        return_value=Response(200, json={"id": 3, "acked_revision": 5, "acked_at": "2024-01-01T00:00:00"})
    )
    from acex_devkit.models.telemetry_agent import TelemetryAgentAck

    result = observability.agents.ack(id=3, payload=TelemetryAgentAck(config_revision=5))
    assert result.acked_revision == 5


@respx.mock
def test_agent_get_returns_full_response_for_manifest_use(observability):
    """Telemetry-agent uses agents.get(id) to poll the manifest-equivalent:
    the agent object itself carries config_revision."""
    respx.get("http://test/api/v1/observability/agents/4").mock(
        return_value=Response(
            200,
            json={
                "id": 4,
                "name": "tele-1",
                "description": "first",
                "config_revision": 7,
                "acked_revision": 3,
                "capabilities": ["icmp"],
                "nodes": [],
                "rules": [],
                "resolved_nodes": [],
                "outputs": [],
            },
        )
    )
    agent = observability.agents.get(4)
    assert agent.config_revision == 7
    assert agent.acked_revision == 3


@respx.mock
def test_agent_outputs_bound(observability):
    respx.get("http://test/api/v1/observability/agents/1/outputs").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": 9,
                        "influxdb_version": "v2",
                        "url": "http://influx:8086",
                        "token": "tok",
                        "organization": "org",
                        "bucket": "bkt",
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    respx.post("http://test/api/v1/observability/agents/1/outputs").mock(
        return_value=Response(
            201,
            json={
                "id": 10,
                "influxdb_version": "v2",
                "url": "http://influx:8086",
            },
        )
    )
    respx.patch("http://test/api/v1/observability/agents/1/outputs/10").mock(
        return_value=Response(
            200,
            json={
                "id": 10,
                "influxdb_version": "v2",
                "url": "http://new:8086",
            },
        )
    )
    respx.delete("http://test/api/v1/observability/agents/1/outputs/10").mock(return_value=Response(204))

    outputs = observability.agents.outputs(1)
    listed = outputs.query()
    assert len(listed) == 1
    assert listed.items[0].id == 9

    new = outputs.create(influxdb_version="v2", url="http://influx:8086", token="t", organization="o", bucket="b")
    assert new.id == 10

    updated = outputs.update(output_id=10, url="http://new:8086")
    assert updated.url == "http://new:8086"

    outputs.delete(output_id=10)


@respx.mock
def test_agent_rules_bound(observability):
    respx.get("http://test/api/v1/observability/agents/1/rules").mock(
        return_value=Response(
            200,
            json={
                "items": [{"id": 1, "region": "eu", "site": "sto"}],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    respx.delete("http://test/api/v1/observability/agents/1/rules/1").mock(return_value=Response(204))

    rules = observability.agents.rules(1)
    listed = rules.query()
    assert len(listed) == 1
    assert listed.items[0].region == "eu"

    rules.delete(rule_id=1)


@respx.mock
def test_grafana_dashboards(observability):
    respx.get("http://test/api/v1/observability/grafana/dashboards").mock(
        return_value=Response(200, json=[{"uid": "abc", "title": "Overview"}])
    )
    respx.get("http://test/api/v1/observability/grafana/dashboards/abc").mock(
        return_value=Response(200, json={"uid": "abc", "title": "Overview", "panels": []})
    )

    listed = observability.grafana.dashboards()
    assert len(listed) == 1
    assert listed[0]["uid"] == "abc"

    dash = observability.grafana.dashboard(uid="abc")
    assert dash["title"] == "Overview"
