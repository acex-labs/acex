"""Assembles and serves the ACE-X API."""

import uvicorn
from acex import AutomationEngine
from acex.database import Connection

from .config import Settings, UnsafeConfiguration


def create_engine(settings: Settings | None = None) -> AutomationEngine:
    """Build an AutomationEngine from the environment.

    Split out from create_app() so deployments that need to register
    integrations or ConfigMap directories can do so before the app is built.
    """
    settings = settings or Settings()

    db = Connection(
        backend=settings.db_backend,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )

    ae = AutomationEngine(db_connection=db, dev_mode=settings.dev)

    # Wire OIDC explicitly rather than leaning on acex.api.auth picking the
    # environment up at import time, so that an unauthenticated API is only
    # ever the result of a deliberate dev-mode start.
    if settings.oidc_issuer_url:
        ae.set_oidc(
            settings.oidc_issuer_url,
            audience=settings.oidc_audience,
            jwks_ttl=settings.oidc_jwks_ttl,
            verify_ssl=settings.oidc_verify_ssl,
        )

    # Left unconfigured the engine adds no CORS middleware, which is what we
    # want: same-origin callers need none, and nothing else is trusted.
    for origin in settings.cors_allowed_origins:
        ae.add_cors_allowed_origin(origin)

    return ae


def create_app(settings: Settings | None = None):
    """Build the FastAPI app (shared by the entry point, the reloader and tests)."""
    settings = settings or Settings()
    settings.check()
    return create_engine(settings).create_app()


def _announce(settings: Settings) -> None:
    if not settings.dev:
        return
    origins = ", ".join(settings.cors_allowed_origins) or "same-origin only"
    auth = "OIDC enabled" if settings.authenticated else "NO AUTH — every endpoint is open"
    print(
        "\n  ACE-X API in dev mode — do not expose this to anyone else."
        f"\n    auth:    {auth}"
        f"\n    origins: {origins}"
        f"\n    reload:  {'on' if settings.reload else 'off'}\n",
        flush=True,
    )


def run(settings: Settings | None = None):
    """Serve the API with uvicorn. Entry point for both ways of starting."""
    settings = settings or Settings()
    settings.check()
    _announce(settings)

    if settings.reload:
        # The reloader re-imports in a subprocess, so hand it a factory to call
        # there instead of an app built here. ACEX_DEV carries dev mode across.
        uvicorn.run(
            "acex_api.app:create_app",
            factory=True,
            host=settings.host,
            port=settings.port,
            reload=True,
        )
    else:
        uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


def main(argv: list[str] | None = None) -> None:
    """Command line for `acex-api` and `python -m acex_api`."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        prog="acex-api",
        description="Serve the ACE-X API.",
        epilog=(
            "Without --dev the service refuses to start unauthenticated or with a "
            "wildcard CORS origin. Everything else is configured through the "
            "environment; see acex_api.config."
        ),
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="run in development mode: allows running without auth, answers any "
        "origin and reloads on source changes. Never use it where others can reach it.",
    )
    parser.add_argument("--host", help="address to bind (default: $ACEX_HOST or 0.0.0.0)")
    parser.add_argument("--port", type=int, help="port to bind (default: $ACEX_PORT or 8080)")
    reload_group = parser.add_mutually_exclusive_group()
    reload_group.add_argument(
        "--reload", dest="reload", action="store_true", default=None, help="restart on source changes"
    )
    reload_group.add_argument(
        "--no-reload", dest="reload", action="store_false", help="do not restart on source changes"
    )
    args = parser.parse_args(argv)

    if args.dev:
        # Set before Settings is built, so that dev mode survives into the
        # reloader subprocess, which re-reads the environment rather than argv.
        os.environ["ACEX_DEV"] = "1"

    settings = Settings()
    if args.host is not None:
        settings.host = args.host
    if args.port is not None:
        settings.port = args.port
    if args.reload is not None:
        settings.reload = args.reload

    try:
        run(settings)
    except UnsafeConfiguration as exc:
        parser.exit(2, f"{exc}\n")
