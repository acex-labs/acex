import logging
import os
import re
import time

import requests as _requests
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

_PUBLIC_PATHS = {"/api/v1/auth/config"}

logger = logging.getLogger("acex.auth")

_UNSAFE_LOG_CHARS = re.compile(r"[^\w.@:+-]")

OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "acex")
_JWKS_TTL = int(os.getenv("OIDC_JWKS_TTL", "3600"))
_JWKS_RETRY_BACKOFF = 30  # seconds between failed JWKS refresh attempts
_JWKS_MAX_STALE = 24 * 3600  # refuse to serve cached JWKS older than this
_VERIFY_SSL = os.getenv("OIDC_VERIFY_SSL", "true").lower() != "false"


def configure(issuer_url: str, audience: str = "acex", jwks_ttl: int = 3600, verify_ssl: bool = True) -> None:
    """Override OIDC settings at runtime (called from AutomationEngine.create_app)."""
    global \
        OIDC_ISSUER_URL, \
        OIDC_AUDIENCE, \
        _JWKS_TTL, \
        _VERIFY_SSL, \
        _jwks, \
        _jwks_fetched_at, \
        _jwks_last_attempt, \
        _oidc_discovery
    OIDC_ISSUER_URL = issuer_url
    OIDC_AUDIENCE = audience
    _JWKS_TTL = jwks_ttl
    _VERIFY_SSL = verify_ssl
    _jwks = None
    _jwks_fetched_at = 0.0
    _jwks_last_attempt = 0.0
    _oidc_discovery = None


_jwks: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_last_attempt: float = 0.0
_oidc_discovery: dict | None = None

_bearer = HTTPBearer(auto_error=False)


def _get_discovery() -> dict | None:
    global _oidc_discovery
    if _oidc_discovery is not None:
        return _oidc_discovery
    if not OIDC_ISSUER_URL:
        return None
    resp = _requests.get(f"{OIDC_ISSUER_URL}/.well-known/openid-configuration", timeout=10, verify=_VERIFY_SSL)
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


def _get_jwks(force_refresh: bool = False) -> dict:
    """Return JWKS keys, refreshing when stale or forced.

    Never discards a working cache: if refresh fails, serve stale keys
    (backoff-throttled, capped at _JWKS_MAX_STALE) instead of raising.
    """
    global _jwks, _jwks_fetched_at, _jwks_last_attempt
    now = time.monotonic()
    if _jwks is not None and not force_refresh and now - _jwks_fetched_at <= _JWKS_TTL:
        return _jwks
    if _jwks is not None and now - _jwks_last_attempt < _JWKS_RETRY_BACKOFF:
        return _jwks  # refresh recently tried and failed — serve stale, don't hammer the IdP
    _jwks_last_attempt = now
    try:
        _jwks = _fetch_jwks()
        _jwks_fetched_at = now
    except Exception as exc:
        if _jwks is None:
            raise  # never fetched — nothing to fall back on
        age = int(now - _jwks_fetched_at)
        if age > _JWKS_MAX_STALE:
            logger.error(
                f"JWKS cache is {age}s old and refresh failed — refusing to serve (max stale {_JWKS_MAX_STALE}s): {exc}"
            )
            raise
        logger.warning(f"JWKS refresh failed, serving stale cache (age={age}s): {exc}")
    return _jwks


def _sub_of(token: str) -> str:
    """Best-effort UNVERIFIED sub claim — for log output only, never trust it.

    Sanitized and length-capped since the value is attacker-controlled
    (prevent log forging).
    """
    try:
        sub = str(jwt.get_unverified_claims(token).get("sub") or "unknown-sub")
    except Exception:
        return "unparseable-token"
    return _UNSAFE_LOG_CHARS.sub("?", sub)[:64]


def _decode(token: str, force_jwks_refresh: bool = False) -> dict:
    return jwt.decode(
        token,
        _get_jwks(force_refresh=force_jwks_refresh),
        algorithms=["RS256"],
        audience=OIDC_AUDIENCE,
        issuer=OIDC_ISSUER_URL,
    )


def _claims_error(exc: JWTError) -> HTTPException:
    msg = str(exc).lower()
    if isinstance(exc, ExpiredSignatureError):
        detail = "Token has expired"
    elif "audience" in msg:
        detail = f"Invalid audience — expected '{OIDC_AUDIENCE}'"
    elif "issuer" in msg:
        detail = f"Invalid issuer — expected '{OIDC_ISSUER_URL}'"
    else:
        detail = f"Token claims invalid: {exc}"
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _idp_unavailable(request: Request, exc: Exception) -> HTTPException:
    """503 when the IdP can't be reached (cold start, outage, stale JWKS cap hit)."""
    logger.error(f"Cannot validate token — identity provider unavailable ({request.method} {request.url.path}): {exc}")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Identity provider unavailable",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> dict:
    if OIDC_ISSUER_URL is None:
        return {}

    if request.url.path in _PUBLIC_PATHS:
        return {}

    if credentials is None:
        logger.warning(
            f"Unauthorized ({request.method} {request.url.path}): request has no (or malformed) Authorization header"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return _decode(credentials.credentials)
    except ExpiredSignatureError as exc:
        # normal client lifecycle (forgotten refresh) — not worth a WARNING
        logger.info(
            f"Token expired ({request.method} {request.url.path}, "
            f"unverified_sub={_sub_of(credentials.credentials)}): {exc}"
        )
        raise _claims_error(exc) from exc
    except JWTClaimsError as exc:
        logger.warning(
            f"JWT validation failed ({request.method} {request.url.path}, "
            f"unverified_sub={_sub_of(credentials.credentials)}): {exc}"
        )
        raise _claims_error(exc) from exc
    except (_requests.RequestException, RuntimeError) as exc:
        raise _idp_unavailable(request, exc) from exc
    except JWTError:
        # Retry once against refreshed JWKS in case of key rotation
        try:
            return _decode(credentials.credentials, force_jwks_refresh=True)
        except (ExpiredSignatureError, JWTClaimsError) as exc:
            logger.warning(
                f"JWT validation failed ({request.method} {request.url.path}, "
                f"unverified_sub={_sub_of(credentials.credentials)}): {exc}"
            )
            raise _claims_error(exc) from exc
        except (_requests.RequestException, RuntimeError) as exc:
            raise _idp_unavailable(request, exc) from exc
        except JWTError as exc:
            logger.warning(
                f"Invalid token signature ({request.method} {request.url.path}, "
                f"unverified_sub={_sub_of(credentials.credentials)}), "
                f"retried with refreshed JWKS: {exc}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
