"""An API with no OIDC issuer configured must not answer as if it were open.

Serving unauthenticated is legitimate while developing, so it is available —
but only by asking for it with Settings(dev=True). A deployment that simply
lost its OIDC_ISSUER_URL is misconfigured, not public: the engine refuses to
build the app, and auth refuses requests should one be built anyway.
"""

import pytest
from acex.api import auth
from acex.automation_engine.automationengine import AutomationEngine
from acex.database import Connection
from acex.settings import Settings, UnsafeConfiguration
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

PROTECTED = "/api/v1/neds"
PUBLIC = "/api/v1/auth/config"
ISSUER = "https://keycloak.example/realms/acex"


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Fresh env + writable cwd (the sqlite db is created there)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACEX_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for name in ("OIDC_ISSUER_URL", "ACEX_DEV", "ACEX_CORS_ALLOWED_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    yield
    auth.configure(None)
    auth.set_dev_mode(False)


def _engine(**settings):
    return AutomationEngine(db_connection=Connection(), settings=Settings(**settings))


class TestWithoutDevMode:
    def should_refuse_to_build_the_app(self):
        with pytest.raises(UnsafeConfiguration, match="OIDC_ISSUER_URL"):
            _engine().create_app()

    def should_refuse_a_wildcard_origin_however_the_engine_is_configured(self):
        engine = _engine(oidc={"issuer_url": ISSUER}, cors={"allowed_origins": ["*"]})
        with pytest.raises(UnsafeConfiguration, match="wildcard"):
            engine.create_app()

    def should_refuse_requests_if_an_open_app_is_built_anyway(self):
        # Defence in depth: auth itself still refuses without an issuer.
        client = TestClient(_engine(dev=True).create_app())
        auth.set_dev_mode(False)
        response = client.get(PROTECTED)
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
        assert client.get(PUBLIC).status_code == 200


class TestWithDevMode:
    def should_serve_a_protected_route_without_a_token(self):
        assert TestClient(_engine(dev=True).create_app()).get(PROTECTED).status_code == 200

    def should_keep_the_public_path_reachable(self):
        assert TestClient(_engine(dev=True).create_app()).get(PUBLIC).status_code == 200


class TestAuthComesFromSettingsOnly:
    def should_ignore_an_issuer_left_in_auth_by_an_earlier_app(self):
        auth.configure(ISSUER)
        _engine(dev=True).create_app()
        assert auth.OIDC_ISSUER_URL is None


class TestDefault:
    def should_not_be_in_dev_mode_unless_asked(self):
        assert _engine().dev_mode is False

    def should_still_accept_the_deprecated_dev_mode_argument(self):
        with pytest.warns(DeprecationWarning):
            engine = AutomationEngine(db_connection=Connection(), dev_mode=True)
        assert engine.settings.dev is True
