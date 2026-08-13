import os

import httpx
from acex_devkit.models.auth_config import AuthConfig

from .authorization_code import AuthorizationCodeAuth
from .client_credentials import ClientCredentialsAuth
from .provider import AuthProvider, NullAuthProvider


def create_auth_provider(api_url: str, verify_ssl: bool = True) -> AuthProvider:
    """Auto-detect: client credentials if env vars present, else interactive.

    issuer_url/client_id come from the backend's /auth/config endpoint unless
    overridden via ACEX_ISSUER_URL / ACEX_CLIENT_ID (e.g. for testing against
    a different issuer than the one the backend is configured with).

    Returns a NullAuthProvider when the backend reports auth is disabled —
    so callers always receive a non-None provider.
    """
    env_verify_ssl = os.environ.get("ACEX_VERIFY_SSL")
    if env_verify_ssl is not None:
        verify_ssl = env_verify_ssl.lower() != "false"

    config = _fetch_auth_config(api_url, verify_ssl)
    if not config.enabled:
        return NullAuthProvider()

    issuer_url = os.environ.get("ACEX_ISSUER_URL") or config.authority
    client_id = os.environ.get("ACEX_CLIENT_ID") or config.client_id

    if client_secret := os.environ.get("ACEX_CLIENT_SECRET"):
        return ClientCredentialsAuth(client_id, client_secret, issuer_url, verify_ssl)

    return AuthorizationCodeAuth(client_id, issuer_url, verify_ssl)


def _fetch_auth_config(api_url: str, verify_ssl: bool) -> AuthConfig:
    resp = httpx.get(f"{api_url}/auth/config", verify=verify_ssl, timeout=10)
    resp.raise_for_status()
    return AuthConfig(**resp.json())


__all__ = [
    "AuthProvider",
    "NullAuthProvider",
    "AuthorizationCodeAuth",
    "ClientCredentialsAuth",
    "create_auth_provider",
]
