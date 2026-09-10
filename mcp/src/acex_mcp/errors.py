"""Translation of backend errors into messages an LLM can act on.

A tool error is read by a model, not a developer: "HTTP 404" tells it nothing,
while "no node instance 42 — use find_nodes() to look one up" tells it what to
do next. Every tool funnels its failures through here.
"""

from acex_client.exceptions import (
    AcexAuthError,
    AcexConnectionError,
    AcexHTTPError,
    AcexNotFoundError,
    AcexPermissionError,
    AcexServerError,
    AcexTimeoutError,
    AcexValidationError,
)
from fastmcp.exceptions import ToolError


def as_tool_error(exc: Exception, *, doing: str) -> ToolError:
    """Map an acex_client exception to a ToolError.

    `doing` describes the attempted operation in a form that reads naturally
    mid-sentence, e.g. "looking up node 42".
    """
    if isinstance(exc, AcexNotFoundError):
        return ToolError(
            f"Not found while {doing}. Check the id exists — use find_nodes() or find_assets() to look it up."
        )
    if isinstance(exc, AcexAuthError):
        return ToolError(
            f"Not authenticated while {doing}. The caller's token was rejected by the ACE-X backend; "
            "it may have expired. Nothing further can be read until the user re-authenticates."
        )
    if isinstance(exc, AcexPermissionError):
        return ToolError(f"Permission denied while {doing}. The authenticated user lacks the required scope.")
    if isinstance(exc, AcexValidationError):
        return ToolError(f"The ACE-X backend rejected the request while {doing}: {exc.body}")
    if isinstance(exc, AcexTimeoutError):
        return ToolError(
            f"Timed out while {doing}. This operation compiles configuration server-side and can be slow; "
            "narrow the request or try a single node instead of a whole site."
        )
    if isinstance(exc, AcexConnectionError):
        return ToolError(f"Cannot reach the ACE-X backend while {doing}. It may be down.")
    if isinstance(exc, AcexServerError):
        return ToolError(
            f"The ACE-X backend failed while {doing} (HTTP {exc.status_code}). This is a server-side fault."
        )
    if isinstance(exc, AcexHTTPError):
        return ToolError(f"Request failed while {doing} (HTTP {exc.status_code}): {exc.body}")
    return ToolError(f"Unexpected failure while {doing}: {exc}")
