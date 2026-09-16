"""Runtime configuration for the ACE-X API service.

Covers what this shell needs to stand the service up: which database to reach,
where to bind, who may call it and how callers authenticate. The `acex` library
reads further environment of its own once running — ACEX_ENCRYPTION_KEY,
VAULT_* — and those stay its own concern rather than being proxied through here.

The service refuses to start on a configuration that would quietly expose it.
Development conveniences live behind an explicit dev mode; see `Settings.dev`.
"""

import os
from dataclasses import dataclass, field


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("false", "0", "no", "")


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class UnsafeConfiguration(RuntimeError):
    """Raised when a production start would expose the API."""


@dataclass
class Settings:
    #: Development mode. Set by `--dev`, which also exports ACEX_DEV so that a
    #: reloader subprocess inherits it. It relaxes the startup checks below —
    #: the API may then run unauthenticated and answer any origin — so it must
    #: never be turned on for a deployment reachable by anyone else.
    dev: bool = field(default_factory=lambda: _flag("ACEX_DEV", False))

    #: Database the AutomationEngine persists to. Migrations run on startup.
    db_backend: str = field(default_factory=lambda: os.environ.get("DB_BACKEND", "postgresql"))
    db_name: str = field(default_factory=lambda: os.environ.get("DB_NAME", "ace"))
    db_user: str = field(default_factory=lambda: os.environ.get("DB_USER", "postgres"))
    db_password: str = field(default_factory=lambda: os.environ.get("DB_PASSWORD", ""))
    db_host: str = field(default_factory=lambda: os.environ.get("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: _int("DB_PORT", 5432))

    #: Where uvicorn binds.
    host: str = field(default_factory=lambda: os.environ.get("ACEX_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _int("ACEX_PORT", 8080))
    #: Restart on source changes. Dev mode turns this on unless told otherwise.
    reload: bool = field(default_factory=lambda: _flag("ACEX_RELOAD", False))

    #: OIDC provider that issues the bearer tokens the API accepts. Without it
    #: every endpoint is open, so it is required outside dev mode.
    oidc_issuer_url: str | None = field(default_factory=lambda: os.environ.get("OIDC_ISSUER_URL") or None)
    oidc_audience: str = field(default_factory=lambda: os.environ.get("OIDC_AUDIENCE", "acex"))
    oidc_jwks_ttl: int = field(default_factory=lambda: _int("OIDC_JWKS_TTL", 3600))
    oidc_verify_ssl: bool = field(default_factory=lambda: _flag("OIDC_VERIFY_SSL", True))

    #: Comma-separated browser origins allowed to make cross-origin calls,
    #: e.g. "https://acex.example.net". Empty by default: no CORS headers are
    #: sent at all, so a browser will only let the API be called from its own
    #: origin. Name the frontend here when it is served from somewhere else.
    #: "*" is rejected outside dev mode — the API sends credentials, and a
    #: wildcard tells Starlette to echo back whatever Origin asks, which trusts
    #: every site on the web.
    cors_allowed_origins: list[str] = field(default_factory=lambda: _list("ACEX_CORS_ALLOWED_ORIGINS", []))

    def __post_init__(self):
        if self.dev:
            # Conveniences, not overrides: an explicit setting still wins.
            if os.environ.get("ACEX_CORS_ALLOWED_ORIGINS") is None:
                self.cors_allowed_origins = ["*"]
            if os.environ.get("ACEX_RELOAD") is None:
                self.reload = True

    @property
    def authenticated(self) -> bool:
        return self.oidc_issuer_url is not None

    def check(self) -> None:
        """Refuse configurations that would expose the API. Called on startup."""
        if self.dev:
            return

        problems = []
        if not self.authenticated:
            problems.append(
                "OIDC_ISSUER_URL is not set, which leaves every endpoint open to "
                "unauthenticated callers. Set it, or pass --dev to run without auth."
            )
        if "*" in self.cors_allowed_origins:
            problems.append(
                'ACEX_CORS_ALLOWED_ORIGINS contains "*". The API sends credentials, so a '
                "wildcard lets any site on the web make authenticated calls on a user's "
                "behalf. Name the origins that need access, or pass --dev."
            )
        if problems:
            raise UnsafeConfiguration("Refusing to start:\n  - " + "\n  - ".join(problems))
