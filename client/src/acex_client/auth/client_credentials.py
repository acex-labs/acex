import os
import time

import requests

from .provider import AuthProvider


class ClientCredentialsAuth(AuthProvider):
    def __init__(self, client_id: str, client_secret: str, issuer_url: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = self._discover_token_url(issuer_url)
        self._token: str | None = None
        self._expires_at: float = 0

    @classmethod
    def from_env(cls) -> "ClientCredentialsAuth":
        client_id = os.environ["ACEX_CLIENT_ID"]
        client_secret = os.environ["ACEX_CLIENT_SECRET"]
        issuer_url = os.environ["ACEX_ISSUER_URL"]
        return cls(client_id, client_secret, issuer_url)

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        self._fetch_token()
        return self._token

    def _fetch_token(self) -> None:
        resp = requests.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 300)

    @staticmethod
    def _discover_token_url(issuer_url: str) -> str:
        url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()["token_endpoint"]
