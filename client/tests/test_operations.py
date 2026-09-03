"""Tests for operations resources via respx mocks."""

from __future__ import annotations

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.operations import OperationsNamespace
from httpx import Response


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@pytest.fixture
def operations(rest):
    return OperationsNamespace(rest)


@respx.mock
def test_compliance_check(operations):
    respx.get("http://test/api/v1/operations/compliance/1").mock(
        return_value=Response(
            200,
            json={
                "total_desired": 10,
                "total_observed": 9,
                "compliant_count": 9,
                "compliance_percentage": 90.0,
            },
        )
    )
    result = operations.compliance.check(node_instance_id=1)
    assert result.total_desired == 10
    assert result.compliance_percentage == 90.0


@respx.mock
def test_compliance_site(operations):
    respx.get("http://test/api/v1/operations/compliance/site/stockholm").mock(
        return_value=Response(
            200,
            json={
                "nodes": {
                    "1": {
                        "total_desired": 5,
                        "total_observed": 5,
                        "compliant_count": 5,
                        "compliance_percentage": 100.0,
                    },
                },
                "summary": {
                    "total_desired": 5,
                    "total_observed": 5,
                    "compliant_count": 5,
                    "compliance_percentage": 100.0,
                },
            },
        )
    )
    result = operations.compliance.site(site_name="stockholm")
    assert "1" in result.nodes or 1 in result.nodes
    assert result.summary.compliant_count == 5


@respx.mock
def test_config_history_list_changes(operations):
    respx.get("http://test/api/v1/operations/configuration/changes").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": 100,
                        "node_instance_id": "1",
                        "hostname": "R1",
                        "site": "sto",
                        "role": "core",
                        "hash": "abc",
                        "created_at": "2024-01-01T00:00:00",
                        "previous_hash": "def",
                        "previous_created_at": "2024-01-02T00:00:00",
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    changes = operations.config_history.list_changes()
    assert changes.total == 1
    assert changes.items[0].hostname == "R1"


@respx.mock
def test_lldp_upload(operations):
    respx.post("http://test/api/v1/operations/lldp_neighbors").mock(
        return_value=Response(200, json={"uploaded": 3, "deduplicated": 1, "re_resolved": 0, "errors": []})
    )
    from acex_devkit.models.lldp_neighbor import LldpNeighborEntry, LldpNeighborUpload

    payload = LldpNeighborUpload(
        node_instance_id=1,
        neighbors=[
            LldpNeighborEntry(local_interface="Gi0/1", remote_device="R2"),
            LldpNeighborEntry(local_interface="Gi0/2", remote_device="R3"),
            LldpNeighborEntry(local_interface="Gi0/1", remote_device="R2"),
        ],
    )
    result = operations.lldp.upload(payload=payload)
    assert result.uploaded == 3
    assert result.deduplicated == 1


@respx.mock
def test_lldp_topology(operations):
    respx.get("http://test/api/v1/operations/lldp_neighbors/topology").mock(
        return_value=Response(
            200,
            json={
                "nodes": [
                    {"id": 1, "label": "R1", "in_inventory": True},
                    {"id": 2, "label": "R2", "in_inventory": True},
                ],
                "edges": [
                    {
                        "source": 1,
                        "target": 2,
                        "source_interface": "Gi0/1",
                        "target_interface": "Gi0/1",
                        "discovery_protocol": "lldp",
                    },
                ],
            },
        )
    )
    topo = operations.lldp.topology(site="stockholm")
    assert len(topo.nodes) == 2
    assert topo.nodes[0].label == "R1"
    assert len(topo.edges) == 1


@respx.mock
def test_lldp_reverse(operations):
    respx.get("http://test/api/v1/operations/lldp_neighbors/2/reverse").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 5,
                    "node_instance_id": 1,
                    "local_interface": "Gi0/1",
                    "remote_device": "R2",
                    "remote_interface": "Gi0/1",
                    "discovery_protocol": "lldp",
                    "remote_node_id": 2,
                    "collected_at": "2024-01-01T00:00:00",
                },
            ],
        )
    )
    result = operations.lldp.reverse(node_instance_id=2)
    assert len(result) == 1
    assert result[0].node_instance_id == 1
