"""acex-client — synchronous Python client for the ACE-X backend."""

from acex_client.client import Acex
from acex_client.exceptions import (
    AcexAuthError,
    AcexConnectionError,
    AcexError,
    AcexHTTPError,
    AcexNotFoundError,
    AcexPermissionError,
    AcexServerError,
    AcexTimeoutError,
    AcexValidationError,
)

__all__ = [
    "Acex",
    "AcexError",
    "AcexHTTPError",
    "AcexNotFoundError",
    "AcexAuthError",
    "AcexPermissionError",
    "AcexValidationError",
    "AcexServerError",
    "AcexTimeoutError",
    "AcexConnectionError",
]
