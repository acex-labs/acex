"""Tests for the top-level Acex facade and context manager."""

from __future__ import annotations

import respx
from acex_client import Acex
from acex_client.auth import NullAuthProvider
from httpx import Response


@respx.mock
def test_acex_constructs_with_null_auth():
    respx.head("http://test/api/v1/ai_ops/ai/ask").mock(return_value=Response(200))
    client = Acex(base_url="http://test/", auth=NullAuthProvider())
    assert client.api_url == "http://test/api/v1"
    assert client.inventory is not None
    assert client.observability is not None
    assert client.operations is not None
    assert client.config_components is not None
    assert client.neds is not None
    assert client.system is not None
    # Ai probe succeeded (HEAD 200)
    assert client.ai is not None
    client.close()


@respx.mock
def test_acex_ai_none_when_ai_ops_unavailable():
    respx.head("http://test/api/v1/ai_ops/ai/ask/").mock(return_value=Response(404))
    client = Acex(base_url="http://test/", auth=NullAuthProvider())
    assert client.ai is None
    client.close()


def test_acex_context_manager_closes():
    # No network: NullAuthProvider + base_url avoid the auth probe that
    # create_auth_provider would do against /auth/config.
    # We inject NullAuthProvider explicitly so no probe request is made.
    with Acex(base_url="http://test/", auth=NullAuthProvider()) as client:
        # ai probe runs; expect it to raise silently → ai is None
        assert client.ai is None


@respx.mock
def test_acex_normalizes_base_url():
    respx.head("http://test/api/v1/ai_ops/ai/ask/").mock(return_value=Response(404))
    # No trailing slash on base_url
    a = Acex(base_url="http://test", auth=NullAuthProvider())
    assert a.api_url == "http://test/api/v1"
    a.close()
    # With trailing slash should give same result
    b = Acex(base_url="http://test/", auth=NullAuthProvider())
    assert b.api_url == "http://test/api/v1"
    b.close()


@respx.mock
def test_acex_full_flow_sites_query(rest_or_acex=None):
    """End-to-end: construct Acex, query sites, verify LiveInstance."""
    respx.head("http://test/api/v1/ai_ops/ai/ask/").mock(return_value=Response(404))
    respx.get("http://test/api/v1/inventory/sites").mock(
        return_value=Response(
            200,
            json={
                "items": [{"id": 1, "name": "stockholm"}],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
    )
    respx.get("http://test/api/v1/inventory/sites/1").mock(
        return_value=Response(200, json={"id": 1, "name": "stockholm"})
    )

    with Acex(base_url="http://test/", auth=NullAuthProvider()) as client:
        result = client.inventory.sites.query()
        assert len(result) == 1
        assert result.items[0].name == "stockholm"

        site = client.inventory.sites.get(1)
        assert site.id == 1
        assert site.name == "stockholm"
