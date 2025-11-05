
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from acex.constants import BASE_URL
from acex import __version__
import os

from pathlib import Path
import importlib

class Api: 

    def create_app(self, automation_engine):

        Api = FastAPI(
            title="ACE-X - Extendable Automation & Control Ecosystem",
            openapi_url=f"{BASE_URL}/openapi.json",
            docs_url=f"{BASE_URL}/docs",
            version = __version__,
            dependencies=[Depends(lambda: automation_engine)]
        )

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