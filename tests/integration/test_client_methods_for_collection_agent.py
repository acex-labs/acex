"""
Interface contract between acex_client and agents/collection-agent.

agents/collection-agent (agent.py, collector.py) drives ACEX purely through
acex_client.Acex. This file checks only that the client side of that boundary
has the shape collection-agent needs: does `Acex` expose the right methods, at
the right place. No backend, no DB, no network — just hasattr()/callable()
checks against a bare `Acex` instance.

Agreed method table (verified against actual collection-agent call sites):

    client.inventory.collection_agents.manifest(id)        GET  /inventory/collection_agents/{id}/manifest
    client.inventory.collection_agents.ack(id, payload=)  POST /inventory/collection_agents/{id}/ack
    client.inventory.collection_agents.report_results(id, payload=)  POST /inventory/collection_agents/{id}/results
    client.inventory.credentials.secret(id)               GET  /inventory/credentials/{id}/secret
    client.inventory.node_instances.upload_observed(id, payload=)  POST /inventory/node_instances/{id}/
                                                                        configuration/observed/
    client.operations.lldp.upload(payload=)               POST /operations/lldp_neighbors/

`neds` is consumed by the agent's `_ensure_neds()` startup sync and by the
collector for loading driver instances:

    client.neds.get_missing()        — returns list of NEDs missing locally
    client.neds.install(ned)          — downloads + pip-installs a NED wheel
    client.neds.get_driver_instance(ned_id) — resolves an installed driver instance
    client.neds.incompatible          — dict of NED name -> why this process does not use it
    Acex(..., ned_interfaces=)       — the NED interfaces the agent can run
"""

import json

import pytest
from acex_client import Acex
from acex_client.auth.provider import AuthProvider
from acex_client.resources.inventory.collection_agents import CollectionAgents
from acex_devkit.models.collection_state import CollectionFailure, CollectionResult, CollectionResultsUpload


class _NoAuth(AuthProvider):
    """Never actually makes a request — Acex.__init__ only calls into the
    auth provider if no `auth=` override is given, and nothing here sends
    a real HTTP request, so the token value is never used."""

    def get_token(self) -> str:
        return "test-token"


@pytest.fixture(scope="module")
def client_shape() -> Acex:
    return Acex(base_url="http://unused.invalid/", auth=_NoAuth())


def _resolves(obj, dotted_path: str) -> bool:
    """Walks `dotted_path` (e.g. "neds.get_missing") off `obj` via getattr,
    stopping (returning False) at the first missing hop instead of raising —
    that's the point: a not-yet-built resource shouldn't crash the check."""
    current = obj
    for part in dotted_path.split("."):
        current = getattr(current, part, None)
        if current is None:
            return False
    return callable(current)


class TestClientInterfaceContract:
    """One assertion per row of the method table in the module docstring.
    Update this list if the table changes — it's the checklist, not the
    other way around."""

    @pytest.mark.parametrize(
        "dotted_path",
        [
            # Methods verified against collection-agent call sites (agent.py, collector.py)
            "inventory.collection_agents.manifest",
            "inventory.collection_agents.ack",
            "inventory.collection_agents.report_results",
            "inventory.credentials.secret",
            "inventory.node_instances.upload_observed",
            "operations.lldp.upload",
            # neds.* used by agent._ensure_neds() — not yet on client
            "neds.get_missing",
            "neds.install",
            "neds.get_driver_instance",
        ],
    )
    def test_method_exists(self, client_shape, dotted_path):
        assert _resolves(client_shape, dotted_path), f"Acex is missing client.{dotted_path}"

    def test_the_results_of_a_round_go_to_the_route_the_backend_has(self):
        sent = []

        class Rest:
            def request(self, method, path, **kwargs):
                sent.append((method, path, json.loads(json.dumps(kwargs["json"]))))
                return {"accepted": 2, "unknown_nodes": [9]}

        upload = CollectionResultsUpload(
            results=[
                CollectionResult(node_id=1, ok=True),
                CollectionResult(node_id=9, ok=False, category=CollectionFailure.privilege_failed, message="no enable"),
            ]
        )

        accepted = CollectionAgents(Rest()).report_results(id=7, payload=upload)

        assert sent == [
            (
                "POST",
                "/inventory/collection_agents/7/results",
                {
                    "results": [
                        {"node_id": 1, "ok": True},
                        {"node_id": 9, "ok": False, "category": "privilege_failed", "message": "no enable"},
                    ]
                },
            )
        ]
        assert (accepted.accepted, accepted.unknown_nodes) == (2, [9])

    def test_neds_say_why_a_driver_is_not_used(self, client_shape):
        assert isinstance(client_shape.neds.incompatible, dict)

    def test_the_client_takes_the_ned_interfaces_the_agent_runs(self):
        client = Acex(base_url="http://unused.invalid/", auth=_NoAuth(), ned_interfaces=[2])

        assert client.neds.ned_interfaces == frozenset({2})
