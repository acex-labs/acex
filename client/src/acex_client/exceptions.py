class AcexError(Exception):
    """Base class for all acex-client errors."""


class AcexHTTPError(AcexError):
    """Base class for HTTP errors returned by the backend."""

    def __init__(self, status_code: int, body: str, message: str | None = None):
        self.status_code = status_code
        self.body = body
        self.message = message or f"HTTP {status_code}"
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.message}: {self.body}"


class AcexNotFoundError(AcexHTTPError):
    """Resource was not found (HTTP 404)."""


class AcexAuthError(AcexHTTPError):
    """Authentication failed (HTTP 401)."""


class AcexPermissionError(AcexHTTPError):
    """Permission denied (HTTP 403)."""


class AcexValidationError(AcexHTTPError):
    """Backend rejected the request payload (HTTP 422)."""


class AcexServerError(AcexHTTPError):
    """Backend server error (HTTP 5xx)."""


class AcexTimeoutError(AcexError):
    """Request timed out."""


class AcexConnectionError(AcexError):
    """Failed to connect to the backend."""


__all__ = [
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
