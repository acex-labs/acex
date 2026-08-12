"""
Interface contract between acex_client and agents/collection-agent.

agents/collection-agent (agent.py, collector.py) drives ACEX purely through
acex_client.acex.acex.Acex. This file checks only that the client side of
that boundary has the shape collection-agent needs:
does `Acex` expose the right methods, at the right place. No backend, no DB,
no network — just hasattr()/callable() checks against a bare `Acex` instance.

Agreed method table. The whole client is being restructured into facades
that mirror the API's own URL-prefix taxonomy (not the OpenAPI tags, which
disagree with the prefix in at least one case — see neds below):

    client.neds.get_missing()                                            GET  /neds/    (diffed against
                                                                                         local entry points)
    client.neds.install(ned)                                             GET  /neds/download/{filename}
    client.neds.get_driver_instance(ned_id)                              (local — resolves an installed entry point,
                                                                                  no request)
    client.inventory.collection_agents.get_manifest(id)                  GET  /inventory/collection_agents/{id}/manifest
    client.inventory.collection_agents.ack_manifest(id, config_revision) POST /inventory/collection_agents/{id}/ack
    client.inventory.credentials.get_secret(id)                          GET  /inventory/credentials/{id}/secret
    client.inventory.node_instances.upload_observed_config(id, content)  POST /inventory/node_instances/{id}..
                                                                                ../configuration/observed/
    client.operations.lldp_neighbors.upload(node_instance_id, neighbors) POST /operations/lldp_neighbors/

`neds` stays top-level rather than under `inventory`: its router prefix is
bare `/neds` (not `/inventory/neds`), even though it's tagged "Inventory" in
the OpenAPI docs. Path wins over tag — the path is the actual contract the
client calls, the tag is just doc grouping.

This table only covers what collection-agent needs. The facade rebuild
itself is broader (also moves the already-existing `node_instances`,
`credentials`, `management_connections`), so other call sites
(cli/src/acex_cli/commands/node.py, client/examples/) need updating too —
tracked wherever that work lands, not in this file.
"""

import pytest
from acex_client.acex.acex import Acex
from acex_client.auth.provider import AuthProvider


class _NoAuth(AuthProvider):
    """Never actually makes a request — Acex.__init__ only calls into the
    auth provider if no `auth=` override is given, and nothing here sends
    a real HTTP request, so the token value is never used."""

    def get_token(self) -> str:
        return "test-token"


@pytest.fixture(scope="module")
def client_shape() -> Acex:
    return Acex(baseurl="http://unused.invalid/", auth=_NoAuth())


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
            "neds.get_missing",
            "neds.install",
            "neds.get_driver_instance",
            "inventory.collection_agents.get_manifest",
            "inventory.collection_agents.ack_manifest",
            "inventory.credentials.get_secret",
            "inventory.node_instances.upload_observed_config",
            "operations.lldp_neighbors.upload",
        ],
    )
    def test_method_exists(self, client_shape, dotted_path):
        assert _resolves(client_shape, dotted_path), f"Acex is missing client.{dotted_path}"
