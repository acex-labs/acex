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
    client.inventory.credentials.secret(id)               GET  /inventory/credentials/{id}/secret
    client.inventory.node_instances.upload_observed(id, payload=)  POST /inventory/node_instances/{id}/
                                                                        configuration/observed/
    client.operations.lldp.upload(payload=)               POST /operations/lldp_neighbors/

`neds` is consumed by the agent's `_ensure_neds()` startup sync and by the
collector for loading driver instances:

    client.neds.get_missing()        — returns list of NEDs missing locally
    client.neds.install(ned)          — downloads + pip-installs a NED wheel
    client.neds.get_driver_instance(ned_id) — resolves an installed driver instance
"""

import pytest
from acex_client import Acex
from acex_client.auth.provider import AuthProvider


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
