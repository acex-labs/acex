import os

from .authorization_code import AuthorizationCodeAuth
from .client_credentials import ClientCredentialsAuth
from .provider import AuthProvider


def create_auth_provider() -> AuthProvider:
    """Auto-detect: client credentials if env vars present, else interactive."""
    if os.environ.get("ACEX_CLIENT_SECRET"):
        return ClientCredentialsAuth.from_env()

    client_id = os.environ.get("ACEX_CLIENT_ID", "acex")
    issuer_url = os.environ["ACEX_ISSUER_URL"]
    return AuthorizationCodeAuth(client_id, issuer_url)


__all__ = [
    "AuthProvider",
    "AuthorizationCodeAuth",
    "ClientCredentialsAuth",
    "create_auth_provider",
]
