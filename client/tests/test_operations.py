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


RUN = {
    "id": 7,
    "type": "acex.operations.actions.ping",
    "state": "queued",
    "jobs": {"queued": 1},
    "created_by": "johan",
    "created_at": "2026-11-26T08:00:00",
}


@respx.mock
def test_actions_run_orders_any_action(operations):
    route = respx.post("http://test/api/v1/operations/actions/ping").mock(return_value=Response(202, json=RUN))
    run = operations.actions.run("ping", [24], target="10.10.0.2", count=5)
    assert run.id == 7
    body = route.calls.last.request.read()
    assert b'"node_ids":[24]' in body.replace(b" ", b"")
    assert b'"target":"10.10.0.2"' in body.replace(b" ", b"")


@respx.mock
def test_actions_ping_is_run_of_ping(operations):
    respx.post("http://test/api/v1/operations/actions/ping").mock(return_value=Response(202, json=RUN))
    assert operations.actions.ping([24], target="10.10.0.2").id == 7


def test_actions_run_checks_params_before_sending(operations):
    with pytest.raises(ValueError, match="No action 'traceroot'"):
        operations.actions.run("traceroot", [24])
    with pytest.raises(ValueError):
        operations.actions.run("ping", [24], count=0)
