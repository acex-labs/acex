import os

from .authorization_code import AuthorizationCodeAuth
from .client_credentials import ClientCredentialsAuth
from .provider import AuthProvider


def create_auth_provider() -> AuthProvider:
    """Auto-detect: client credentials if env vars present, else interactive."""
    verify_ssl = os.environ.get("ACEX_VERIFY_SSL").lower()

    client_id = os.environ.get("ACEX_CLIENT_ID", "acex")
    issuer_url = os.environ["ACEX_ISSUER_URL"]
    if verify_ssl == "false":
        verify_ssl = False
    else:
        verify_ssl = True

    if client_secret := os.environ.get("ACEX_CLIENT_SECRET"):
        return ClientCredentialsAuth(client_id, client_secret, issuer_url, verify_ssl)

    return AuthorizationCodeAuth(client_id, issuer_url, verify_ssl)


__all__ = [
    "AuthProvider",
    "AuthorizationCodeAuth",
    "ClientCredentialsAuth",
    "create_auth_provider",
]
