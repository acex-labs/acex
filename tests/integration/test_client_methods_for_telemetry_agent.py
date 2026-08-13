"""
Interface contract between acex_client and agents/telemetry-agent.

agents/telemetry-agent (agent.py) drives ACEX purely through acex_client.Acex.
This file checks only that the client side of that boundary has the shape
telemetry-agent needs: does `Acex` expose the right methods, at the right
place. No backend, no DB, no network — just hasattr()/callable() checks
against a bare `Acex` instance.

Agreed method table (verified against actual telemetry-agent call sites):

    client.observability.agents.get(id)              GET  /observability/agents/{id}
    client.observability.agents.config(id)           GET  /observability/agents/{id}/config
    client.observability.agents.ack(id, payload=)    POST /observability/agents/{id}/ack

The telemetry-agent polls the agent object itself (which carries
`config_revision`) as its manifest, fetches the rendered telegraf config
via `/config`, and acks via `/ack`.
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
    """Walks `dotted_path` (e.g. "observability.agents.get") off `obj` via getattr,
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
            "observability.agents.get",
            "observability.agents.config",
            "observability.agents.ack",
        ],
    )
    def test_method_exists(self, client_shape, dotted_path):
        assert _resolves(client_shape, dotted_path), f"Acex is missing client.{dotted_path}"
