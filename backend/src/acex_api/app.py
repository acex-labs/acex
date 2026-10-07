"""Assembles and serves the ACE-X API."""

import uvicorn
from acex import AutomationEngine
from acex.settings import Settings, UnsafeConfiguration


def create_engine(settings: Settings | None = None) -> AutomationEngine:
    """Build an AutomationEngine from settings (read from the environment if omitted).

    Split out from create_app() so deployments that need to register
    integrations or ConfigMap directories can do so before the app is built.
    The engine's own create_app() runs the same startup checks.
    """
    return AutomationEngine(settings=settings or Settings())


def create_app(settings: Settings | None = None):
    """Build the FastAPI app (shared by the entry point, the reloader and tests)."""
    return create_engine(settings).create_app()


def _announce(settings: Settings) -> None:
    if not settings.dev:
        return
    origins = ", ".join(settings.cors.allowed_origins) or "same-origin only"
    auth = "OIDC enabled" if settings.authenticated else "NO AUTH — every endpoint is open"
    print(
        "\n  ACE-X API in dev mode — do not expose this to anyone else."
        f"\n    auth:    {auth}"
        f"\n    origins: {origins}"
        f"\n    reload:  {'on' if settings.server.reload else 'off'}\n",
        flush=True,
    )


def run(settings: Settings | None = None):
    """Serve the API with uvicorn. Entry point for both ways of starting."""
    settings = settings or Settings()
    # Checked here as well as in create_app() so that a refused start fails
    # before uvicorn, and the reloader, are started.
    settings.check()
    _announce(settings)

    server = settings.server
    if server.reload:
        # The reloader re-imports in a subprocess, so hand it a factory to call
        # there instead of an app built here. ACEX_DEV carries dev mode across.
        uvicorn.run(
            "acex_api.app:create_app",
            factory=True,
            host=server.host,
            port=server.port,
            reload=True,
        )
    else:
        uvicorn.run(create_app(settings), host=server.host, port=server.port)


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
            "environment; see acex.settings."
        ),
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="run in development mode: allows running without auth, answers any "
        "origin and reloads on source changes. Never use it where others can reach it.",
    )
    parser.add_argument("--host", help="address to bind (default: $ACEX_SERVER_HOST or 0.0.0.0)")
    parser.add_argument("--port", type=int, help="port to bind (default: $ACEX_SERVER_PORT or 8080)")
    reload_group = parser.add_mutually_exclusive_group()
    reload_group.add_argument(
        "--reload", dest="reload", action="store_true", default=None, help="restart on source changes"
    )
    reload_group.add_argument(
        "--no-reload", dest="reload", action="store_false", help="do not restart on source changes"
    )
    args = parser.parse_args(argv)

    if args.dev:
        # Exported rather than passed as Settings(dev=True), so that dev mode
        # survives into the reloader subprocess, which re-reads the environment.
        os.environ["ACEX_DEV"] = "1"

    try:
        settings = Settings()
        if args.host is not None:
            settings.server.host = args.host
        if args.port is not None:
            settings.server.port = args.port
        if args.reload is not None:
            settings.server.reload = args.reload
        run(settings)
    except UnsafeConfiguration as exc:
        parser.exit(2, f"{exc}\n")
