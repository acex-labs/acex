"""GET /api/v1/services tells the frontend which other backends this deployment
has and where they are. Only ACEX knows; the frontend is told nothing else."""

from types import SimpleNamespace

import pytest
from acex.api import auth
from acex.api.routers.services import create_router
from acex.automation_engine.automationengine import AutomationEngine
from acex.database import Connection
from acex.settings import ServicesSettings, Settings
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACEX_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for name in ("ACEX_OIDC_ISSUER_URL", "ACEX_DEV", "ACEX_CORS_ALLOWED_ORIGINS", "ACEX_SERVICES_SAMRUAI_URL"):
        monkeypatch.delenv(name, raising=False)
    yield
    auth.configure(None)
    auth.set_dev_mode(False)


def _get(services: ServicesSettings) -> dict:
    app = FastAPI()
    app.include_router(create_router(SimpleNamespace(settings=SimpleNamespace(services=services))))
    return TestClient(app).get("/api/v1/services").json()


def should_list_nothing_when_no_service_is_configured():
    assert _get(ServicesSettings()) == {}


def should_list_a_configured_service_by_name():
    assert _get(ServicesSettings(samruai_url="https://samruai.example.net")) == {
        "samruai": {"url": "https://samruai.example.net"}
    }


def should_read_the_url_from_the_environment(monkeypatch):
    monkeypatch.setenv("ACEX_SERVICES_SAMRUAI_URL", "http://localhost:8082/")
    assert Settings().services.samruai_url == "http://localhost:8082"


@pytest.mark.parametrize(
    "url",
    ["samruai.example.net", "javascript:alert(1)", "ftp://samruai.example.net", "https://x.example/?a=1"],
)
def should_refuse_anything_but_a_plain_http_url(url):
    with pytest.raises(ValidationError):
        ServicesSettings(samruai_url=url)


def should_answer_without_a_token_when_auth_is_on():
    # The frontend reads it while it starts, before it may have a token.
    engine = AutomationEngine(
        db_connection=Connection(),
        settings=Settings(oidc={"issuer_url": "https://keycloak.example/realms/acex"}),
    )
    client = TestClient(engine.create_app())
    assert client.get("/api/v1/services").status_code == 200
    assert client.get("/api/v1/neds").status_code == 401
