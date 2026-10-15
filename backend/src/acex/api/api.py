import importlib
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from acex.api import auth as _auth
from acex.constants import BASE_URL
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware


class Api:
    def create_app(self, automation_engine):

        settings = automation_engine.settings

        # Set before anything can serve a request: without it an engine with no
        # OIDC issuer refuses requests rather than answering them unauthenticated.
        _auth.set_dev_mode(settings.dev)

        # Always configured from settings, also when no issuer is set, so auth
        # never depends on what the environment held when auth.py was imported.
        _auth.configure(
            settings.oidc.issuer_url,
            settings.oidc.audience,
            settings.oidc.jwks_ttl,
            settings.oidc.verify_ssl,
        )

        @asynccontextmanager
        async def lifespan(app):
            if not _auth.OIDC_ISSUER_URL:
                if settings.dev:
                    print("AUTH: dev mode — no OIDC issuer configured, every endpoint is open")
                else:
                    print("AUTH: no OIDC issuer configured — requests will be refused with 503")
            if _auth.OIDC_ISSUER_URL:
                try:
                    keys = _auth._get_jwks().get("keys", [])
                    print(f"OIDC: fetched {len(keys)} JWKS key(s) from {_auth.OIDC_ISSUER_URL}")
                except Exception as exc:
                    print(f"OIDC: failed to fetch JWKS — {exc}")
            yield

        Api = FastAPI(
            title="ACE-X - Extendable Automation & Control Ecosystem",
            openapi_url=f"{BASE_URL}/openapi.json",
            docs_url=f"{BASE_URL}/docs",
            version=version("acex"),
            lifespan=lifespan,
            dependencies=[Depends(lambda: automation_engine), Depends(_auth.get_current_user)],
        )

        if settings.oidc.issuer_url is not None:
            _original_openapi = Api.openapi

            def _custom_openapi():
                if Api.openapi_schema:
                    return Api.openapi_schema
                schema = _original_openapi()
                discovery = _auth._get_discovery()
                if discovery:
                    schema.setdefault("components", {}).setdefault("securitySchemes", {})["OIDCLogin"] = {
                        "type": "oauth2",
                        "flows": {
                            "authorizationCode": {
                                "authorizationUrl": discovery["authorization_endpoint"],
                                "tokenUrl": discovery["token_endpoint"],
                                "scopes": {
                                    "openid": "OpenID Connect identity",
                                    "profile": "User profile",
                                    "email": "Email address",
                                },
                            }
                        },
                    }
                Api.openapi_schema = schema
                return schema

            Api.openapi = _custom_openapi

        # No origins configured means no CORS middleware at all: same-origin
        # callers need none, and nothing else is trusted.
        if settings.cors.allowed_origins:
            Api.add_middleware(
                CORSMiddleware,
                allow_origins=settings.cors.allowed_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        routers = []
        routers_path = Path(__file__).parent / "routers"
        for file in routers_path.glob("*.py"):
            if file.name == "__init__.py":
                continue
            module_name = f"acex.api.routers.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "create_router"):
                    router = module.create_router(automation_engine)
                    if router is not None:
                        routers.append(router)
            except Exception as e:
                print(f"Failed to import {module_name}: {e}")
                raise e

        for router in routers:
            Api.include_router(router)

        return Api
