"""Integration tests for inventory resources via respx mocks."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.exceptions import AcexNotFoundError
from acex_client.http import RestClient
from acex_client.resources.inventory import InventoryNamespace
from httpx import Response


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@pytest.fixture
def inventory(rest):
    return InventoryNamespace(rest)


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------


@respx.mock
def test_sites_crud(inventory):
    respx.post("http://test/api/v1/inventory/sites").mock(
        return_value=Response(201, json={"id": 1, "name": "stockholm", "city": "SE"})
    )
    respx.get("http://test/api/v1/inventory/sites/1").mock(
        return_value=Response(200, json={"id": 1, "name": "stockholm", "city": "SE"})
    )
    respx.patch("http://test/api/v1/inventory/sites/1").mock(
        return_value=Response(200, json={"id": 1, "name": "sthlm", "city": "SE"})
    )
    respx.delete("http://test/api/v1/inventory/sites/1").mock(return_value=Response(204))

    site = inventory.sites.create(name="stockholm", city="SE")
    assert site.id == 1
    assert site.name == "stockholm"

    fetched = inventory.sites.get(1)
    assert fetched.city == "SE"

    fetched.name = "sthlm"
    fetched.save()

    fetched.delete()


# ---------------------------------------------------------------------------
# Collection agents — action + bound sub-resource
# ---------------------------------------------------------------------------


@respx.mock
def test_collection_agent_ack_action(inventory):
    route = respx.post("http://test/api/v1/inventory/collection_agents/1/ack").mock(
        return_value=Response(200, json={"id": 1, "acked_revision": 5, "acked_at": "2024-01-01T00:00:00"})
    )
    result = inventory.collection_agents.ack(
        id=1,
        payload=__import__(
            "acex_devkit.models.collection_agent",
            fromlist=["CollectionAgentAck"],
        ).CollectionAgentAck(config_revision=5),
    )
    assert route.called
    assert result.acked_revision == 5


@respx.mock
def test_collection_agent_manifest(inventory):
    respx.get("http://test/api/v1/inventory/collection_agents/2/manifest").mock(
        return_value=Response(
            200,
            json={
                "agent_id": 2,
                "name": "agent-2",
                "config_revision": 3,
                "interval_seconds": 60,
                "enabled": True,
                "targets": [
                    {
                        "node_id": 10,
                        "hostname": "r1",
                        "target_ip": "10.0.0.1",
                        "connection_type": "ssh",
                        "ned_id": "cisco-ios",
                        "vendor": "cisco",
                        "os": "ios",
                        "credentials": {"ssh": 7},
                    },
                ],
            },
        )
    )
    m = inventory.collection_agents.manifest(id=2)
    assert m.agent_id == 2
    assert len(m.targets) == 1
    assert m.targets[0].node_id == 10
    assert m.targets[0].credentials == {"ssh": 7}


@respx.mock
def test_collection_agent_rules_bound(inventory):
    respx.get("http://test/api/v1/inventory/collection_agents/1/rules").mock(
        return_value=Response(
            200,
            json={
                "items": [{"id": 7, "region": "eu", "site": "sto"}],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    respx.post("http://test/api/v1/inventory/collection_agents/1/rules").mock(
        return_value=Response(201, json={"id": 8, "region": "us"})
    )
    respx.delete("http://test/api/v1/inventory/collection_agents/1/rules/8").mock(return_value=Response(204))

    rules = inventory.collection_agents.rules(1)
    listed = rules.query()
    assert len(listed) == 1
    assert listed.items[0].region == "eu"

    new_rule = rules.create(region="us")
    assert new_rule.id == 8

    rules.delete(rule_id=8)


# ---------------------------------------------------------------------------
# Credentials + secret action
# ---------------------------------------------------------------------------


@respx.mock
def test_credential_secret_action(inventory):
    respx.get("http://test/api/v1/inventory/credentials/5/secret").mock(
        return_value=Response(200, json={"id": 5, "credential_type": "ssh", "fields": {"password": "hunter2"}})
    )
    secret = inventory.credentials.secret(id=5)
    assert secret.id == 5
    assert secret.fields == {"password": "hunter2"}


@respx.mock
def test_node_credentials_bound_subresource(inventory):
    respx.get("http://test/api/v1/inventory/nodes/3/credentials").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {"id": 1, "node_id": 3, "credential_id": 5, "credential_name": "ssh", "credential_type": "ssh"}
                ],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    creds = inventory.node_credentials(3)
    listed = creds.query()
    assert len(listed) == 1
    assert listed.items[0].credential_name == "ssh"


# ---------------------------------------------------------------------------
# Node instances — operational configuration actions
# ---------------------------------------------------------------------------


@respx.mock
def test_node_instance_configuration_desired(inventory):
    respx.get("http://test/api/v1/inventory/node_instances/1/configuration/desired").mock(
        return_value=Response(200, text="hostname R1\n!")
    )
    config = inventory.node_instances.configuration_desired(id=1)
    assert "hostname R1" in config


@respx.mock
def test_node_instance_upload_and_list_observed(inventory):
    respx.post("http://test/api/v1/inventory/node_instances/1/configuration/observed/").mock(
        return_value=Response(
            200,
            json={
                "id": 100,
                "hash": "abc",
                "created_at": "2024-01-01T00:00:00",
                "node_instance_id": "1",
            },
        )
    )
    respx.get("http://test/api/v1/inventory/node_instances/1/configuration/observed/").mock(
        return_value=Response(
            200, json=[{"id": 100, "hash": "abc", "created_at": "2024-01-01T00:00:00", "node_instance_id": "1"}]
        )
    )

    from acex_devkit.models.config_snapshot import DeviceConfigUpload

    result = inventory.node_instances.upload_observed(id=1, payload=DeviceConfigUpload(content="! config\n"))
    assert result["hash"] == "abc"

    snapshots = inventory.node_instances.list_observed(id=1)
    assert len(snapshots) == 1
    assert snapshots[0].hash == "abc"


@respx.mock
def test_node_instance_observed_diff(inventory):
    respx.get("http://test/api/v1/inventory/node_instances/1/configuration/observed/diff").mock(
        return_value=Response(
            200,
            json={
                "config_a": {"hash": "abc", "created_at": "2024-01-01T00:00:00"},
                "config_b": {"hash": "def", "created_at": "2024-01-02T00:00:00"},
                "diff": [
                    {"type": "equal", "line_a": 1, "line_b": 1, "text": "hostname R1"},
                    {"type": "add", "line_b": 2, "text": "interface Gi0/1"},
                ],
                "stats": {"added": 1, "removed": 0, "equal": 1},
            },
        )
    )
    diff = inventory.node_instances.diff_observed(id=1, a=100, b=200)
    assert diff.config_a.hash == "abc"
    assert diff.stats.added == 1
    assert diff.diff[1].type == "add"


@respx.mock
def test_node_instance_pending_actions_404(inventory):
    # Try a non-existent config_id on manifest — ensure 404 raises NotFound.
    respx.get("http://test/api/v1/inventory/collection_agents/999/manifest").mock(
        return_value=Response(404, json={"detail": "not found"})
    )
    with pytest.raises(AcexNotFoundError):
        inventory.collection_agents.manifest(id=999)


# ---------------------------------------------------------------------------
# Logical nodes — configuration action
# ---------------------------------------------------------------------------


@respx.mock
def test_logical_node_configuration(inventory):
    respx.get("http://test/api/v1/inventory/logical_nodes/5/configuration").mock(
        return_value=Response(
            200,
            json={
                "id": 5,
                "hostname": "R1",
                "role": "core",
                "site": "stockholm",
                "sequence": 1,
                "configuration": {
                    "system": {"config": {"hostname": "R1"}},
                    "interfaces": {},
                    "network_instances": {},
                    "stp": {},
                    "lacp": {},
                    "lldp": {},
                    "cdp": {},
                    "acl": {},
                },
                "meta_data": {},
                "regions": ["eu"],
            },
        )
    )
    config = inventory.logical_nodes.configuration(id=5)
    assert config.hostname == "R1"
    assert config.regions == ["eu"]
