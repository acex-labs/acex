"""The about endpoint reports the backend's version, its build id, and the
versions of every installed acex package and NED driver."""

import os
from importlib.metadata import entry_points, version
from types import SimpleNamespace

from acex.api.routers.health import create_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(inventory=None, device_config_manager=None)))
    return TestClient(app)


def test_about_response_shape():
    data = _client().get("/api/v1/health/about").json()
    assert set(data) == {"version", "build_id", "build_ref", "python", "packages", "drivers"}
    assert isinstance(data["python"], str)
    assert isinstance(data["packages"], dict)
    assert isinstance(data["drivers"], list)


def test_about_reports_backend_version():
    data = _client().get("/api/v1/health/about").json()
    assert data["version"] == version("acex")
    assert data["build_id"] == (os.environ.get("ACEX_BUILD_ID") or None)
    assert data["build_ref"] == (os.environ.get("ACEX_BUILD_REF") or None)


def test_about_lists_acex_packages():
    data = _client().get("/api/v1/health/about").json()
    assert data["packages"]["acex"] == version("acex")
    assert data["packages"]["acex-devkit"] == version("acex-devkit")
    assert all(name.startswith("acex") for name in data["packages"])


def test_about_lists_ned_drivers():
    data = _client().get("/api/v1/health/about").json()
    expected = sorted(ep.value.split(":")[-1] for ep in entry_points(group="acex.neds"))
    assert [d["name"] for d in data["drivers"]] == expected
    assert all(d["package"] and d["version"] for d in data["drivers"])


def test_about_reports_the_branch_the_build_ran_on(monkeypatch):
    monkeypatch.setenv("ACEX_BUILD_REF", "dev")
    assert _client().get("/api/v1/health/about").json()["build_ref"] == "dev"
    monkeypatch.setenv("ACEX_BUILD_REF", "")
    assert _client().get("/api/v1/health/about").json()["build_ref"] is None
