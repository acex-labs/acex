"""Startup guards for the deployable API service.

The API is open to anyone when OIDC is unconfigured, and a wildcard CORS origin
lets any site make credentialed calls. Both are legitimate locally, so they are
allowed only behind an explicit dev mode — these tests pin that boundary.
"""

import pytest
from acex_api.config import Settings, UnsafeConfiguration

ISSUER = "https://keycloak.example/realms/acex"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "ACEX_DEV",
        "ACEX_RELOAD",
        "ACEX_CORS_ALLOWED_ORIGINS",
        "OIDC_ISSUER_URL",
    ):
        monkeypatch.delenv(name, raising=False)


class TestProductionGuards:
    def should_refuse_to_start_without_an_oidc_issuer(self):
        with pytest.raises(UnsafeConfiguration, match="OIDC_ISSUER_URL"):
            Settings().check()

    def should_refuse_a_wildcard_origin(self, monkeypatch):
        monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "*")
        with pytest.raises(UnsafeConfiguration, match="credentials"):
            Settings().check()

    def should_report_every_problem_at_once(self, monkeypatch):
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "*")
        with pytest.raises(UnsafeConfiguration) as exc:
            Settings().check()
        assert "OIDC_ISSUER_URL" in str(exc.value)
        assert "wildcard" in str(exc.value)

    def should_start_with_auth_and_no_cross_origin_trust(self, monkeypatch):
        monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
        settings = Settings()
        settings.check()
        assert settings.authenticated
        assert settings.cors_allowed_origins == []

    def should_start_with_named_origins(self, monkeypatch):
        monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "https://a.example, https://b.example")
        settings = Settings()
        settings.check()
        assert settings.cors_allowed_origins == ["https://a.example", "https://b.example"]


class TestDevMode:
    def should_allow_running_without_auth(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        settings = Settings()
        settings.check()
        assert not settings.authenticated

    def should_default_to_answering_any_origin(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        assert Settings().cors_allowed_origins == ["*"]

    def should_let_an_explicit_origin_win(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "https://a.example")
        assert Settings().cors_allowed_origins == ["https://a.example"]

    def should_keep_auth_when_an_issuer_is_configured(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        monkeypatch.setenv("OIDC_ISSUER_URL", ISSUER)
        assert Settings().authenticated

    def should_reload_by_default_but_yield_to_an_explicit_setting(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        assert Settings().reload is True
        monkeypatch.setenv("ACEX_RELOAD", "false")
        assert Settings().reload is False


class TestDevModeIsNeverImplicit:
    def should_stay_off_unless_asked(self):
        assert Settings().dev is False

    @pytest.mark.parametrize("value", ["0", "false", "no", ""])
    def should_treat_falsy_values_as_off(self, monkeypatch, value):
        monkeypatch.setenv("ACEX_DEV", value)
        assert Settings().dev is False
