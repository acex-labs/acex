
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from acex.constants import BASE_URL
from acex import __version__
from acex.api import auth as _auth
import os

from pathlib import Path
import importlib

class Api:

    def create_app(self, automation_engine):

        if automation_engine.oidc_issuer_url is not None:
            _auth.configure(
                automation_engine.oidc_issuer_url,
                automation_engine.oidc_audience,
                automation_engine.oidc_jwks_ttl,
                automation_engine.oidc_verify_ssl,
            )

        @asynccontextmanager
        async def lifespan(app):
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
            version=__version__,
            lifespan=lifespan,
            dependencies=[Depends(lambda: automation_engine), Depends(_auth.get_current_user)],
        )

        if automation_engine.oidc_issuer_url is not None:
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

        if automation_engine.cors_settings_default is False:
            Api.add_middleware(
                CORSMiddleware,
                allow_origins=automation_engine.cors_allowed_origins,
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
                    router = getattr(module, "create_router")(automation_engine)
                    if router is not None:
                        routers.append(router)
            except Exception as e:
                print(f"Failed to import {module_name}: {e}")
                raise e

        for router in routers:
            Api.include_router(router)

        return Api