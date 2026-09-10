"""The single path from a tool to the ACE-X backend.

Two things matter here.

**The MCP server holds no credentials of its own.** Over HTTP it forwards the
caller's bearer token verbatim, so every read is authorized as that user by the
backend. A service account would make this server a confused deputy: anyone who
reached its port would get fleet-wide read access. Over stdio there is no
inbound request, so the process authenticates as the user through acex_client's
own env/browser flow instead.

**The token is per-request, the connection pool is not.** One shared `Acex`
instance keeps httpx's pool warm; the token travels in a ContextVar that
`_ContextTokenAuth` reads on each request. `asyncio.to_thread` copies the
current context, so the token set by the tool coroutine is visible to the
synchronous client running in the worker thread.
"""

import asyncio
import contextvars
import logging
from collections.abc import Callable
from typing import Any

from acex_client import Acex
from acex_client.auth import AuthProvider, create_auth_provider

from .config import settings
from .errors import as_tool_error

logger = logging.getLogger("acex_mcp.backend")

_caller_token: contextvars.ContextVar[str | None] = contextvars.ContextVar("acex_caller_token", default=None)


class _ContextTokenAuth(AuthProvider):
    """Yields whichever token the current request put in context."""

    def get_token(self) -> str:
        return _caller_token.get() or ""


def set_caller_token(token: str | None) -> None:
    _caller_token.set(token)


_client: Acex | None = None


def client() -> Acex:
    """The process-wide backend client, built on first use.

    Construction is lazy because in HTTP mode it must not depend on the backend
    being reachable at import time.
    """
    global _client
    if _client is None:
        auth: AuthProvider
        if settings.is_stdio:
            # No inbound request to borrow a token from — authenticate as the
            # user running us (client-credentials env vars, or browser flow).
            auth = create_auth_provider(f"{settings.api_url}/api/v1", settings.verify_ssl)
        else:
            auth = _ContextTokenAuth()
        _client = Acex(
            base_url=settings.api_url,
            verify=settings.verify_ssl,
            auth=auth,
            timeout=settings.request_timeout,
        )
        logger.info("backend client ready (%s, transport=%s)", settings.api_url, settings.transport)
    return _client


async def call[T](fn: Callable[..., T], *args: Any, doing: str, **kwargs: Any) -> T:
    """Run a synchronous acex_client call off the event loop.

    acex_client is sync (httpx.Client), so calling it directly from a tool
    coroutine would block every other in-flight request.
    """
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except Exception as exc:
        logger.info("backend call failed while %s: %s", doing, exc)
        raise as_tool_error(exc, doing=doing) from exc


async def get_json(path: str, *, params: dict[str, Any] | None = None, doing: str) -> Any:
    """Fetch a raw JSON body, bypassing acex_client's typed models.

    Used only for `intent_diff`, whose `Diff` model carries a `component_type:
    type[Any]` field that does not survive a JSON round-trip — validating the
    response back into it would fail. Everything else goes through the typed
    resource methods.
    """
    return await call(client().rest.request, "GET", path, params=params, doing=doing)
