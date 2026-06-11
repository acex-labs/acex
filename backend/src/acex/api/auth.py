import os
import time
import requests as _requests
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_PUBLIC_PATHS = {"/api/v1/auth/config"}
from jose import jwt, JWTError

OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "acex")
_JWKS_TTL = int(os.getenv("OIDC_JWKS_TTL", "3600"))
_VERIFY_SSL = os.getenv("OIDC_VERIFY_SSL", "true").lower() != "false"


def configure(issuer_url: str, audience: str = "acex", jwks_ttl: int = 3600, verify_ssl: bool = True) -> None:
    """Override OIDC settings at runtime (called from AutomationEngine.create_app)."""
    global OIDC_ISSUER_URL, OIDC_AUDIENCE, _JWKS_TTL, _VERIFY_SSL, _jwks, _jwks_fetched_at, _oidc_discovery
    OIDC_ISSUER_URL = issuer_url
    OIDC_AUDIENCE = audience
    _JWKS_TTL = jwks_ttl
    _VERIFY_SSL = verify_ssl
    _jwks = None
    _jwks_fetched_at = 0.0
    _oidc_discovery = None

_jwks: dict | None = None
_jwks_fetched_at: float = 0.0
_oidc_discovery: dict | None = None

_bearer = HTTPBearer(auto_error=False)


def _get_discovery() -> dict | None:
    global _oidc_discovery
    if _oidc_discovery is not None:
        return _oidc_discovery
    if not OIDC_ISSUER_URL:
        return None
    resp = _requests.get(
        f"{OIDC_ISSUER_URL}/.well-known/openid-configuration", timeout=10, verify=_VERIFY_SSL
    )
    resp.raise_for_status()
    _oidc_discovery = resp.json()
    return _oidc_discovery


def _fetch_jwks() -> dict:
    discovery = _get_discovery()
    if discovery is None:
        raise RuntimeError("OIDC_ISSUER_URL not set")
    resp = _requests.get(discovery["jwks_uri"], timeout=10, verify=_VERIFY_SSL)
    resp.raise_for_status()
    return resp.json()


def _get_jwks() -> dict:
    global _jwks, _jwks_fetched_at
    if _jwks is None or time.monotonic() - _jwks_fetched_at > _JWKS_TTL:
        _jwks = _fetch_jwks()
        _jwks_fetched_at = time.monotonic()
    return _jwks


def _decode(token: str) -> dict:
    return jwt.decode(
        token,
        _get_jwks(),
        algorithms=["RS256"],
        audience=OIDC_AUDIENCE,
        issuer=OIDC_ISSUER_URL,
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if OIDC_ISSUER_URL is None:
        return {}

    if request.url.path in _PUBLIC_PATHS:
        return {}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return _decode(credentials.credentials)
    except JWTError as exc:
        # one retry with a fresh JWKS in case of key rotation
        global _jwks
        _jwks = None
        try:
            return _decode(credentials.credentials)
        except JWTError as exc2:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            )
