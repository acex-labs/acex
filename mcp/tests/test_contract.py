"""Guards against the failure mode that broke the previous implementation.

Its tools called endpoints that had been moved or had never existed, and
described fields the API does not return. Nothing caught it, because nothing
checked the tools against the API. Two layers do that here:

* the client methods the tools call must still exist (runs in CI, no backend)
* the paths behind them must still be in the backend's OpenAPI spec (runs only
  when a backend is reachable)
"""

import os

import httpx
import pytest
from acex_client import Acex
from acex_client.auth.provider import NullAuthProvider

#: Every client call the tools make. Renaming one of these in acex_client
#: without updating the tools would otherwise only surface at runtime, as a
#: tool error handed to a model.
CLIENT_METHODS = [
    ("inventory.node_instances", "query"),
    ("inventory.node_instances", "get"),
    ("inventory.node_instances", "configuration_desired"),
    ("inventory.node_instances", "list_observed"),
    ("inventory.node_instances", "get_latest_observed"),
    ("inventory.node_instances", "get_observed"),
    ("inventory.node_instances", "diff_observed"),
    ("inventory.assets", "query"),
    ("inventory.sites", "query"),
    ("inventory.regions", "query"),
    ("operations.lldp", "get"),
    ("operations.lldp", "reverse"),
]

#: Paths the tools reach, relative to /api/v1.
BACKEND_PATHS = [
    "/inventory/node_instances",
    "/inventory/node_instances/{id}",
    "/inventory/node_instances/{id}/configuration/desired",
    "/inventory/node_instances/{id}/configuration/observed",
    "/inventory/node_instances/{id}/configuration/observed/latest",
    "/inventory/node_instances/{id}/configuration/observed/{config_id}",
    "/inventory/node_instances/{id}/configuration/observed/diff",
    "/inventory/node_instances/{id}/configuration/intent_diff",
    "/inventory/assets",
    "/inventory/sites",
    "/inventory/regions",
    "/operations/lldp_neighbors/{node_instance_id}",
    "/operations/lldp_neighbors/{node_instance_id}/reverse",
    # get_running_config is a placeholder and calls no endpoint of its own.
]


@pytest.fixture(scope="module")
def offline_client():
    """A client that is never called — only introspected for its method names."""
    return Acex(base_url="http://127.0.0.1:1", auth=NullAuthProvider())


@pytest.mark.parametrize(("namespace", "method"), CLIENT_METHODS)
def test_client_method_exists(offline_client, namespace, method):
    target = offline_client
    for part in namespace.split("."):
        target = getattr(target, part)
    assert callable(getattr(target, method, None)), f"acex_client no longer has {namespace}.{method}()"


def _spec() -> dict:
    base = os.environ.get("ACEX_API_URL", "http://localhost:8080").rstrip("/")
    try:
        resp = httpx.get(f"{base}/api/v1/openapi.json", timeout=5)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"no backend at {base} to check the API contract against: {exc}")
    return resp.json()


@pytest.mark.parametrize("path", BACKEND_PATHS)
def test_backend_still_serves_path(path):
    paths = _spec().get("paths", {})
    assert f"/api/v1{path}" in paths, f"the backend no longer serves /api/v1{path}"
