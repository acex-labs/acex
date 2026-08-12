import time

import httpx

from .provider import AuthProvider


class ClientCredentialsAuth(AuthProvider):
    def __init__(self, client_id: str, client_secret: str, issuer_url: str, verify_ssl: bool):
        self._client_id = client_id
        self._client_secret = client_secret
        self.verify = verify_ssl
        self._token_url = self._discover_token_url(issuer_url)
        self._token: str | None = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        self._fetch_token()
        return self._token

    def _fetch_token(self) -> None:
        resp = httpx.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            verify=self.verify,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 300)

    def _discover_token_url(self, issuer_url: str) -> str:
        url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        resp = httpx.get(url, verify=self.verify)
        resp.raise_for_status()
        return resp.json()["token_endpoint"]


__all__ = ["ClientCredentialsAuth"]
