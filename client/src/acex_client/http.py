from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from acex_client.auth.provider import AuthProvider
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

_STATUS_MAP: dict[int, type[AcexHTTPError]] = {
    401: AcexAuthError,
    403: AcexPermissionError,
    404: AcexNotFoundError,
    422: AcexValidationError,
}


class _BearerAuth(httpx.Auth):
    """httpx.Auth that injects a Bearer token from an AuthProvider on each request."""

    def __init__(self, auth: AuthProvider):
        self._auth = auth

    def auth_flow(self, request: httpx.Request) -> Iterator[httpx.Request]:
        token = self._auth.get_token()
        if token:
            request.headers["Authorization"] = f"Bearer {token}"
        yield request


class RestClient:
    """Thin wrapper around httpx.Client that maps responses to Acex* exceptions.

    All higher layers (Resource mixins, @action, @stream) call `request()`
    / `stream()` here. URL is built by the caller as a path relative to
    `base_url` (e.g. `/inventory/sites/42`).
    """

    def __init__(
        self,
        base_url: str,
        auth: AuthProvider,
        *,
        verify: bool = True,
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.auth = auth
        self.verify = verify
        self._client = httpx.Client(
            base_url=base_url,
            auth=_BearerAuth(auth),
            verify=verify,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RestClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        raw: bool = False,
    ) -> Any:
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as e:
            raise AcexTimeoutError(str(e)) from e
        except httpx.ConnectError as e:
            raise AcexConnectionError(str(e)) from e
        return self._handle(response, raw=raw)

    def stream(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Iterator[str]:
        """Issue a request expecting an SSE text/event-stream response.

        Yields the `data:` field of each SSE event as a string. Lines that
        are not `data:` lines (e.g. `event:` or comments) are skipped.
        """
        try:
            with self._client.stream("POST", path, params=params, json=json) as response:
                if response.status_code >= 400:
                    response.read()
                    self._raise_for_status(response.status_code, response.text)
                for line in response.iter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        continue
                    if line.startswith("data:"):
                        yield line[5:].lstrip()
        except httpx.TimeoutException as e:
            raise AcexTimeoutError(str(e)) from e
        except httpx.ConnectError as e:
            raise AcexConnectionError(str(e)) from e

    def _handle(self, response: httpx.Response, *, raw: bool = False) -> Any:
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            self._raise_for_status(response.status_code, response.text)
        if raw:
            return response.text
        if not response.content:
            return None
        return response.json()

    @staticmethod
    def _raise_for_status(status_code: int, body: str) -> None:
        exc_class = _STATUS_MAP.get(status_code) or (AcexServerError if status_code >= 500 else AcexHTTPError)
        raise exc_class(status_code, body)


__all__ = ["RestClient"]
