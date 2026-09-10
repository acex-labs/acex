"""Token pass-through and the refusal to start without knowing the auth rules."""

import asyncio

import httpx
import pytest
from acex_client.http import _BearerAuth
from acex_mcp import auth as auth_module
from acex_mcp.backend import _ContextTokenAuth, set_caller_token


def _header_for(token: str | None) -> str | None:
    """The Authorization header acex_client would actually send."""
    set_caller_token(token)
    flow = _BearerAuth(_ContextTokenAuth()).auth_flow(httpx.Request("GET", "http://backend/api/v1/anything"))
    return next(flow).headers.get("Authorization")


def test_callers_token_is_forwarded():
    assert _header_for("caller-jwt") == "Bearer caller-jwt"


def test_no_token_sends_no_header():
    """With auth disabled there is no token, and an empty bearer header would
    be rejected outright rather than treated as anonymous."""
    assert _header_for(None) is None


async def test_concurrent_callers_do_not_share_a_token():
    """The reason the token lives in a ContextVar rather than on the client:
    one shared client would send whichever token was set last to everyone."""

    async def seen_by(token: str) -> str | None:
        set_caller_token(token)
        await asyncio.sleep(0)  # force interleaving
        return _ContextTokenAuth().get_token()

    first, second = await asyncio.gather(seen_by("alice-jwt"), seen_by("bob-jwt"))
    assert first == "alice-jwt"
    assert second == "bob-jwt"


def test_stdio_has_no_inbound_auth():
    """Over a pipe from a process the user launched there is no request to
    authenticate; the client authenticates as the user itself instead."""
    assert auth_module.settings.is_stdio
    assert auth_module.build_verifier() is None


def test_unreachable_backend_refuses_to_start(monkeypatch):
    """Never silently serve unauthenticated because the backend was down when
    we asked whether authentication is required."""
    monkeypatch.setattr(auth_module.settings, "transport", "http")
    monkeypatch.setattr(auth_module.settings, "api_url", "http://127.0.0.1:1")
    with pytest.raises(auth_module.AuthUnavailableError):
        auth_module.build_verifier()


def test_auth_disabled_backend_serves_without_auth(monkeypatch):
    monkeypatch.setattr(auth_module.settings, "transport", "http")

    def fake_get(url, **kwargs):
        return httpx.Response(200, json={"enabled": False}, request=httpx.Request("GET", url))

    monkeypatch.setattr(auth_module.httpx, "get", fake_get)
    assert auth_module.build_verifier() is None
