"""Cross-cutting request handling: token propagation and tool-call logging."""

import logging
import time
from typing import Any

from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware.middleware import CallNext, Middleware, MiddlewareContext

from .backend import set_caller_token

logger = logging.getLogger("acex_mcp.middleware")


class CallerTokenMiddleware(Middleware):
    """Puts the verified caller's token where the backend client can find it.

    Runs on every message so tools, resources and prompts all act as the
    caller. In stdio mode there is no access token and this is a no-op — the
    backend client authenticates as the user itself.
    """

    async def on_message(self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]) -> Any:
        token = get_access_token()
        set_caller_token(token.token if token else None)
        return await call_next(context)


class ToolLoggingMiddleware(Middleware):
    """One log line per tool call, with duration and calling subject.

    An AI-facing surface is opaque without this: when an answer is wrong, the
    first question is which tools were actually called and what they returned.
    """

    async def on_call_tool(self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]) -> Any:
        token = get_access_token()
        subject = token.client_id if token else "anonymous"
        name = getattr(context.message, "name", "?")
        started = time.monotonic()
        try:
            result = await call_next(context)
        except Exception as exc:
            logger.warning(
                "tool %s failed for %s after %.0fms: %s",
                name,
                subject,
                (time.monotonic() - started) * 1000,
                exc,
            )
            raise
        logger.info("tool %s ok for %s in %.0fms", name, subject, (time.monotonic() - started) * 1000)
        return result
