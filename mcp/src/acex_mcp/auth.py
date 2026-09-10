"""Inbound authentication, configured from the backend.

The backend is the only place OIDC is configured, so this server asks it rather
than duplicating OIDC_* env vars: `GET /api/v1/auth/config` is public and
reports the issuer (as `authority`) and the expected audience (as `client_id`).

Note what this is *for*. It is not a second layer of protection over the data —
the backend authorizes every read regardless. It exists so an external client
gets a proper 401 pointing at the OAuth metadata and can start a login flow, so
an expired token fails once at the boundary instead of becoming N tool errors
fed to the model as prose, and so calls can be logged per user.
"""

import logging

import httpx
from fastmcp.server.auth.providers.jwt import JWTVerifier

from .config import settings

logger = logging.getLogger("acex_mcp.auth")


class AuthUnavailableError(RuntimeError):
    """The backend could not be asked what the auth settings are."""


def _discover(authority: str) -> str:
    resp = httpx.get(
        f"{authority.rstrip('/')}/.well-known/openid-configuration",
        verify=settings.verify_ssl,
        timeout=10,
    )
    resp.raise_for_status()
    jwks_uri = resp.json().get("jwks_uri")
    if not jwks_uri:
        raise AuthUnavailableError(f"OIDC discovery at {authority} returned no jwks_uri")
    return jwks_uri


def build_verifier() -> JWTVerifier | None:
    """Build a token verifier from the backend's auth config.

    Returns None when the backend reports auth disabled — the server then runs
    unauthenticated, mirroring the backend so a Keycloak-less dev stack works.

    Raises AuthUnavailableError if the backend cannot be reached, so startup
    fails loudly rather than silently serving without auth.
    """
    if settings.is_stdio:
        # The transport is a pipe from a process the user started themselves;
        # there is no inbound request to authenticate.
        return None

    try:
        resp = httpx.get(f"{settings.api_url}/api/v1/auth/config", verify=settings.verify_ssl, timeout=10)
        resp.raise_for_status()
        config = resp.json()
    except Exception as exc:
        raise AuthUnavailableError(
            f"Cannot read auth config from {settings.api_url} — refusing to start without knowing "
            f"whether authentication is required: {exc}"
        ) from exc

    if not config.get("enabled"):
        logger.warning("backend reports auth disabled — serving MCP without inbound authentication")
        return None

    authority = config["authority"]
    audience = config.get("client_id")
    verifier = JWTVerifier(jwks_uri=_discover(authority), issuer=authority, audience=audience)
    logger.info("inbound auth enabled (issuer=%s, audience=%s)", authority, audience)
    return verifier
