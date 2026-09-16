"""An API with no OIDC issuer configured must not answer as if it were open.

Serving unauthenticated is legitimate while developing, so it is available —
but only by asking for it with AutomationEngine(dev_mode=True). A deployment
that simply lost its OIDC_ISSUER_URL is misconfigured, not public.
"""

import pytest
from acex.automation_engine.automationengine import AutomationEngine
from acex.database import Connection
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

PROTECTED = "/api/v1/neds"
PUBLIC = "/api/v1/auth/config"


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Fresh env + writable cwd (the sqlite db is created there)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACEX_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("OIDC_ISSUER_URL", raising=False)
    # auth.py reads the issuer at import time; clear what earlier tests left.
    from acex.api import auth

    monkeypatch.setattr(auth, "OIDC_ISSUER_URL", None)
    yield


def _client(**kwargs):
    engine = AutomationEngine(db_connection=Connection(), **kwargs)
    return TestClient(engine.create_app())


class TestWithoutDevMode:
    def should_refuse_a_protected_route_rather_than_serve_it_open(self):
        response = _client().get(PROTECTED)
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    def should_refuse_even_when_a_bearer_token_is_offered(self):
        response = _client().get(PROTECTED, headers={"Authorization": "Bearer whatever"})
        assert response.status_code == 503

    def should_keep_the_public_path_reachable_for_the_healthcheck(self):
        assert _client().get(PUBLIC).status_code == 200


class TestWithDevMode:
    def should_serve_a_protected_route_without_a_token(self):
        assert _client(dev_mode=True).get(PROTECTED).status_code == 200

    def should_keep_the_public_path_reachable(self):
        assert _client(dev_mode=True).get(PUBLIC).status_code == 200


class TestDefault:
    def should_not_be_in_dev_mode_unless_asked(self):
        assert AutomationEngine(db_connection=Connection()).dev_mode is False
