import logging
import re
import time

import requests as _requests
from acex import permissions as _permissions
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

# Both are read by the frontend while it starts, before it may have a token.
# Neither holds anything the frontend's own static config would not.
_PUBLIC_PATHS = {"/api/v1/auth/config", "/api/v1/services"}
_PUBLIC_PATH_PREFIXES = ("/api/v1/ztp",)
# A git host calls this when a branch has a new commit. It cannot sign in, so the route checks the secret of the
# repository itself (see acex.git_sync.webhook).
_PUBLIC_PATH_PATTERNS = (re.compile(r"^/api/v1/git_repositories/\d+/webhook$"),)

logger = logging.getLogger("acex.auth")

_UNSAFE_LOG_CHARS = re.compile(r"[^\w.@:+-]")
#: A role is logged as it is written where it is safe to: a pattern has a star, a group of a directory has slashes.
_UNSAFE_ROLE_CHARS = re.compile(r"[^\w.@:+*/-]")

# Set from Settings.oidc by configure() when the app is built; never read from
# the environment here, so there is one source for them.
OIDC_ISSUER_URL: str | None = None
OIDC_AUDIENCE = "acex"
_JWKS_TTL = 3600
_JWKS_RETRY_BACKOFF = 30  # seconds between failed JWKS refresh attempts
_JWKS_MAX_STALE = 24 * 3600  # refuse to serve cached JWKS older than this
_VERIFY_SSL = True

#: How permissions are checked (see AuthorizationSettings and acex.permissions). Set from Settings.authz by
#: configure_authorization() when the app is built. Off until set, so nothing is refused that was not before. Each group
#: of routes has a mode of its own: AUTHZ_MODE is for reading a device login in the clear ("credentials"),
#: OPERATIONS_AUTHZ_MODE for running commands on devices, reading what they answered and handing out the broker's login
#: ("operations").
AUTHZ_MODE = "off"
OPERATIONS_AUTHZ_MODE = "off"
_MODES = ("off", "log", "enforce")
_ROLES_CLAIMS: tuple[str, ...] = ("realm_access.roles", "resource_access.{audience}.roles")
#: The roles of the settings, each with the permissions it holds. The backend names none of its own: a role is made in
#: the identity provider, out of permissions, or here.
_BUNDLES: dict[str, frozenset[str]] = {}
#: A request that would be refused is logged once per caller and route in this many seconds, not on every call: an
#: agent asks for a login per node in every round.
_LOG_EVERY = 600.0
_logged_denials: dict[tuple, float] = {}
#: How many of a token's roles a log line names. A token can list hundreds of groups.
_LOGGED_ROLES = 20

#: Serving an API with no OIDC issuer configured means serving it to anyone.
#: That is only ever acceptable while developing locally, so it has to be asked
#: for: Settings(dev=True). Otherwise such a deployment is treated as
#: misconfigured and refuses to answer rather than answering unauthenticated.
_DEV_MODE = False


def set_dev_mode(enabled: bool) -> None:
    """Allow serving without authentication (called from AutomationEngine.create_app)."""
    global _DEV_MODE
    _DEV_MODE = enabled


def configure(issuer_url: str | None, audience: str = "acex", jwks_ttl: int = 3600, verify_ssl: bool = True) -> None:
    """Set OIDC settings (called from AutomationEngine.create_app)."""
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
        raise RuntimeError("ACEX_OIDC_ISSUER_URL not set")
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
    # Public by design: the frontend reads this before it has a token, and the
    # container healthcheck polls it. Kept reachable however auth is configured.
    if (
        request.url.path in _PUBLIC_PATHS
        or any(
            request.url.path == prefix or request.url.path.startswith(f"{prefix}/") for prefix in _PUBLIC_PATH_PREFIXES
        )
        or any(pattern.match(request.url.path) for pattern in _PUBLIC_PATH_PATTERNS)
    ):
        return {}

    if OIDC_ISSUER_URL is None:
        if _DEV_MODE:
            return {}
        logger.error(
            f"Refusing ({request.method} {request.url.path}): no OIDC issuer is configured, so no "
            "request can be authenticated. Configure OIDC, or enable dev mode to run open."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this deployment",
        )

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


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> str | None:
    """The caller's raw bearer token, for forwarding to a downstream service.

    `get_current_user` returns decoded claims and discards the token string, so
    a route that must act *as* the caller further downstream (the MCP tool
    server) needs the original credential. Validity is already enforced by the
    global `get_current_user` dependency; this only hands the string over.
    """
    return credentials.credentials if credentials else None


def require_scopes(*required: str):
    """Dependency factory: reject with 403 (and log) if the token lacks any of the given scopes.

    Reads the OIDC `scope` claim from the validated token, e.g.:
        Depends(require_scopes("nodes:read", "nodes:write"))
    """

    def dep(request: Request, user: dict = Depends(get_current_user)) -> dict:  # noqa: B008
        if OIDC_ISSUER_URL is None:
            return user  # auth disabled — allow everything
        granted = set(str(user.get("scope", "")).split())
        missing = [s for s in required if s not in granted]
        if missing:
            logger.warning(
                f"Authorization denied ({request.method} {request.url.path}): "
                f"user '{user.get('sub', 'unknown')}' missing scope(s) {missing}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope(s): {', '.join(missing)}",
            )
        return user

    return dep


def configure_authorization(
    mode: str,
    roles_claims: list[str] | tuple[str, ...],
    operations_mode: str = "off",
    bundles: dict[str, list[str]] | None = None,
) -> None:
    """Set how permissions are checked (called from AutomationEngine.create_app). `bundles` are the roles of the
    settings, each with the permissions it holds; there are no others. A permission, a name or a mode that does not
    exist raises ValueError, which stops the API from starting instead of refusing somebody later."""
    global AUTHZ_MODE, OPERATIONS_AUTHZ_MODE, _ROLES_CLAIMS, _BUNDLES
    for value in (mode, operations_mode):
        if value not in _MODES:
            raise ValueError(f"{value!r} is not a mode of the permission checks. They are: {', '.join(_MODES)}")
    resolved = _permissions.resolve_bundles(bundles)
    AUTHZ_MODE = mode
    OPERATIONS_AUTHZ_MODE = operations_mode
    _ROLES_CLAIMS = tuple(roles_claims)
    _BUNDLES = resolved
    _logged_denials.clear()


def roles_of(claims: dict) -> set[str]:
    """The roles a token lists, read from the paths in the settings. A path that is missing, or holds anything but a
    list of names or one string of names, is skipped."""
    roles: set[str] = set()
    for path in _ROLES_CLAIMS:
        value = claims
        for key in path.replace("{audience}", OIDC_AUDIENCE).split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, str):
            value = value.split()
        if isinstance(value, list):
            roles.update(item for item in value if isinstance(item, str))
    return roles


def permissions_of(claims: dict) -> set[str]:
    """The permissions a token holds: what each of its roles stands for. A role is a role of the settings, a
    permission, or a pattern of permissions; any other role, such as Keycloak's `offline_access` or a role of the
    identity provider that is made of permissions, holds nothing by its name."""
    held: set[str] = set()
    for role in roles_of(claims):
        if role in _BUNDLES:
            held |= _BUNDLES[role]
        else:
            held |= {name for name in _permissions.PERMISSIONS if _permissions.matches(role, name)}
    return held


def _mode_of(group: str) -> str:
    return OPERATIONS_AUTHZ_MODE if group == _permissions.OPERATIONS else AUTHZ_MODE


def _held_by(permission: str) -> list[str]:
    """The roles of the settings that hold a permission, by name."""
    return sorted(role for role, held in _BUNDLES.items() if permission in held)


def _roles_for_the_log(claims: dict) -> str:
    """What a refused token does carry, for whoever reads the log. A role that is there and holds nothing has to be
    made of permissions in the identity provider, or be listed in the settings. The names come from the token, so
    they are cleaned and cut before they are written."""
    roles = sorted(_UNSAFE_ROLE_CHARS.sub("?", role)[:64] for role in roles_of(claims))
    if not roles:
        return "it lists no roles"
    more = f" and {len(roles) - _LOGGED_ROLES} more" if len(roles) > _LOGGED_ROLES else ""
    return f"its roles are {', '.join(roles[:_LOGGED_ROLES])}{more}"


def require_permission(name: str):
    """Dependency factory: the caller's token must hold the permission: list it among its roles, or carry a role of
    the settings that holds it (see acex.permissions). What happens when it does not depends on the mode of the group
    of routes the permission belongs to: nothing (off), a log line and the request goes on (log), or 403 (enforce).
    Without an OIDC issuer there are no roles to check, as for `require_scopes`.

        Depends(require_permission("operations.execute"))
    """
    permission = _permissions.PERMISSIONS[name]  # a name that does not exist fails when the route is made

    def dep(request: Request, user: dict = Depends(get_current_user)) -> dict:  # noqa: B008
        mode = _mode_of(permission.group)
        if mode == "off" or OIDC_ISSUER_URL is None:
            return user
        if name in permissions_of(user):
            return user
        route = getattr(request.scope.get("route"), "path", request.url.path)
        who = _UNSAFE_LOG_CHARS.sub("?", str(user.get("azp") or user.get("sub") or "unknown"))[:64]
        holders = _held_by(name)
        by = f" (held by the roles {', '.join(holders)})" if holders else ""
        has = _roles_for_the_log(user)
        if mode == "log":
            key, now = (who, request.method, route), time.monotonic()
            if now - _logged_denials.get(key, -_LOG_EVERY) >= _LOG_EVERY:
                _logged_denials[key] = now
                logger.warning(
                    f"Would be refused ({request.method} {route}): '{who}' does not hold the permission {name}{by}; "
                    f"{has}. Set {_permissions.MODE_SETTINGS[permission.group]}=enforce once every caller has a role "
                    "that holds it."
                )
            return user
        logger.warning(
            f"Authorization denied ({request.method} {route}): '{who}' does not hold the permission {name}{by}; {has}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires the permission {name}{by}",
        )

    dep.permission = name  # type: ignore[attr-defined]  # read by describe_permission_rules()
    return dep


def describe_permission_rules(router) -> None:
    """Say in each route's description which permission it needs, which roles of the settings hold it and which
    setting turns the check on, from the rule the route has, so that the API documentation and the check cannot
    disagree. Called on a router before it is included in the app, since an app keeps the routers it includes as they
    are."""
    for route in router.routes:
        for dependency in getattr(route, "dependencies", []):
            name = getattr(dependency.dependency, "permission", None)
            if name is None:
                continue
            permission = _permissions.PERMISSIONS[name]
            holders = _held_by(name)
            by = f"The roles {', '.join(f'`{role}`' for role in holders)} of the settings hold it. " if holders else ""
            note = (
                f"**Permission:** `{name}`, to {permission.summary}. {by}Checked when "
                f"`{_permissions.MODE_SETTINGS[permission.group]}` is `enforce` (403 without it) and only logged when "
                "it is "
                f"`log`; `off`, the default, checks nothing."
            )
            route.description = f"{route.description}\n\n{note}" if route.description else note


def authorization_overview() -> dict:
    """How this installation checks permissions, for `GET /auth/permissions`: the permissions, and the roles of the
    settings with what they hold."""
    return {
        "modes": {
            group: {"setting": setting, "mode": _mode_of(group)}
            for group, setting in _permissions.MODE_SETTINGS.items()
        },
        "roles_claims": list(_ROLES_CLAIMS),
        "permissions": [
            {
                "name": p.name,
                "summary": p.summary,
                "group": p.group,
                "sensitive": p.sensitive,
                "roles": _held_by(p.name),
            }
            for p in _permissions.PERMISSIONS.values()
        ],
        "roles": {role: sorted(held) for role, held in sorted(_BUNDLES.items())},
    }
