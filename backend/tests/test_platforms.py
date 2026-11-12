"""The platform catalog: declared hardware, what installed NEDs support of it, and what the installation enabled."""

import asyncio
from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.platforms import create_router
from acex.inventory.asset_service import AssetService
from acex.platforms import HardwareModelManager
from acex.plugins.neds.manager import NEDManager
from acex_devkit.models.asset import AssetUpdate
from acex_devkit.models.ned import Platform
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

ENABLED = "/api/v1/platforms/enabled_models"


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


@pytest.fixture
def hardware_models():
    return HardwareModelManager(_Db())


@pytest.fixture
def api(hardware_models, monkeypatch):
    # One NED: IOS XE on the C9300-24T only.
    nedded = [Platform(vendor="cisco", os="cisco_iosxe", hardware_models=["C9300-24T"])]
    monkeypatch.setattr(NEDManager, "platforms", lambda self: nedded)
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(hardware_models=hardware_models)))
    app.dependency_overrides[auth.get_current_user] = lambda: {"preferred_username": "alice"}
    return TestClient(app)


def model(api, hardware_model: str) -> dict:
    catalog = api.get("/api/v1/platforms").json()
    return next(m for v in catalog["vendors"] for m in v["hardware_models"] if m["hardware_model"] == hardware_model)


def test_a_model_is_supported_on_the_os_a_ned_declares_for_it(api):
    assert model(api, "C9300-24T")["supported_os"] == ["cisco_iosxe"]
    assert model(api, "C9300-48P")["supported_os"] == []


def test_no_model_is_enabled_until_someone_enables_it(api):
    assert model(api, "C9300-24T")["enabled"] is False

    assert api.put(f"{ENABLED}/c9300-24t").status_code == 204

    assert model(api, "C9300-24T")["enabled"] is True


def test_a_model_name_may_hold_a_slash(api):
    assert api.put(f"{ENABLED}/CISCO1941%2FK9").status_code == 204
    assert model(api, "CISCO1941/K9")["enabled"] is True


def test_an_undeclared_model_can_not_be_enabled(api):
    assert api.put(f"{ENABLED}/NOT-A-SWITCH").status_code == 404


def test_a_model_can_be_disabled_again(api):
    api.put(f"{ENABLED}/C9300-24T")

    assert api.delete(f"{ENABLED}/C9300-24T").status_code == 204
    assert api.delete(f"{ENABLED}/C9300-24T").status_code == 204  # already disabled

    assert model(api, "C9300-24T")["enabled"] is False


class _Adapter:
    """Stores nothing: the asset service only needs the call to succeed."""

    def create(self, asset):
        return asset

    def update(self, id, asset):
        return asset


def test_an_asset_entering_the_inventory_enables_its_declared_model(hardware_models):
    assets = AssetService(_Adapter(), hardware_models)

    asyncio.run(assets.create(SimpleNamespace(hardware_model="c9300-48p")))
    asyncio.run(assets.create(SimpleNamespace(hardware_model="HOMEMADE-1")))
    asyncio.run(assets.update("1", AssetUpdate(hardware_model="C9300-24T")))

    assert hardware_models.enabled() == {"C9300-48P", "C9300-24T"}
