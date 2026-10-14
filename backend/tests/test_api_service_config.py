"""Startup guards and resolution order for the engine's Settings.

The API is open to anyone when OIDC is unconfigured, and a wildcard CORS origin
lets any site make credentialed calls. Both are legitimate locally, so they are
allowed only behind an explicit dev mode — these tests pin that boundary, and
that it holds however the engine is started.
"""

import pytest
from acex.settings import (
    DatabaseSettings,
    InfluxDBOutput,
    InfluxDBSettings,
    OidcSettings,
    RabbitMQSettings,
    Section,
    Settings,
    UnsafeConfiguration,
)

ISSUER = "https://keycloak.example/realms/acex"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "ACEX_DEV",
        "ACEX_SERVER_RELOAD",
        "ACEX_SERVER_FORWARDED_ALLOW_IPS",
        "ACEX_CORS_ALLOWED_ORIGINS",
        "ACEX_OIDC_ISSUER_URL",
        "ACEX_OIDC_AUDIENCE",
        "ACEX_DB_HOST",
        "ACEX_DB_NAME",
        "ACEX_DB__HOST",
        "ACEX_CREDENTIALS_ENCRYPTION_KEY",
        "ACEX_CREDENTIALS__ENCRYPTION_KEY",
        "ACEX_INFLUXDB_URL",
        "ACEX_INFLUXDB_TOKEN",
        "ACEX_INFLUXDB_EXTRA_OUTPUTS",
        "ACEX_RABBITMQ_HOST",
        "ACEX_RABBITMQ_PORT",
        "ACEX_RABBITMQ_VHOST",
        "ACEX_RABBITMQ_USER",
        "ACEX_RABBITMQ_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


class TestProductionGuards:
    def should_refuse_to_start_without_an_oidc_issuer(self):
        with pytest.raises(UnsafeConfiguration, match="ACEX_OIDC_ISSUER_URL"):
            Settings().check()

    def should_refuse_a_wildcard_origin(self, monkeypatch):
        monkeypatch.setenv("ACEX_OIDC_ISSUER_URL", ISSUER)
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "*")
        with pytest.raises(UnsafeConfiguration, match="credentials"):
            Settings().check()

    def should_report_every_problem_at_once(self, monkeypatch):
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "*")
        with pytest.raises(UnsafeConfiguration) as exc:
            Settings().check()
        assert "ACEX_OIDC_ISSUER_URL" in str(exc.value)
        assert "wildcard" in str(exc.value)

    def should_start_with_auth_and_no_cross_origin_trust(self, monkeypatch):
        monkeypatch.setenv("ACEX_OIDC_ISSUER_URL", ISSUER)
        settings = Settings()
        settings.check()
        assert settings.authenticated
        assert settings.cors.allowed_origins == []

    def should_start_with_named_origins(self, monkeypatch):
        monkeypatch.setenv("ACEX_OIDC_ISSUER_URL", ISSUER)
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "https://a.example, https://b.example")
        settings = Settings()
        settings.check()
        assert settings.cors.allowed_origins == ["https://a.example", "https://b.example"]


class TestDevMode:
    def should_allow_running_without_auth(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        settings = Settings()
        settings.check()
        assert not settings.authenticated

    def should_default_to_answering_any_origin(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        assert Settings().cors.allowed_origins == ["*"]

    def should_let_an_explicit_origin_win(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "https://a.example")
        assert Settings().cors.allowed_origins == ["https://a.example"]

    def should_let_an_explicitly_empty_origin_list_win(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        monkeypatch.setenv("ACEX_CORS_ALLOWED_ORIGINS", "")
        assert Settings().cors.allowed_origins == []

    def should_keep_auth_when_an_issuer_is_configured(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        monkeypatch.setenv("ACEX_OIDC_ISSUER_URL", ISSUER)
        assert Settings().authenticated

    def should_reload_by_default_but_yield_to_an_explicit_setting(self, monkeypatch):
        monkeypatch.setenv("ACEX_DEV", "1")
        assert Settings().server.reload is True
        monkeypatch.setenv("ACEX_SERVER_RELOAD", "false")
        assert Settings().server.reload is False

    def should_apply_the_same_conveniences_when_set_in_code(self):
        settings = Settings(dev=True)
        assert settings.cors.allowed_origins == ["*"]
        assert settings.server.reload is True


class TestDevModeIsNeverImplicit:
    def should_stay_off_unless_asked(self):
        assert Settings().dev is False

    @pytest.mark.parametrize("value", ["0", "false", "no", ""])
    def should_treat_falsy_values_as_off(self, monkeypatch, value):
        monkeypatch.setenv("ACEX_DEV", value)
        assert Settings().dev is False


class TestResolutionOrder:
    """Code, then environment, then default — for whole settings and for single sections."""

    def should_let_code_win_over_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_DB_HOST", "from-env")
        assert Settings(db=DatabaseSettings(host="from-code")).db.host == "from-code"

    def should_fill_a_section_given_as_a_dict_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_OIDC_AUDIENCE", "from-env")
        settings = Settings(oidc={"issuer_url": ISSUER})
        assert settings.oidc.issuer_url == ISSUER
        assert settings.oidc.audience == "from-env"

    def should_fill_a_section_given_as_an_instance_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_OIDC_AUDIENCE", "from-env")
        assert Settings(oidc=OidcSettings(issuer_url=ISSUER)).oidc.audience == "from-env"

    def should_fill_untouched_sections_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_DB_NAME", "from-env")
        assert Settings(dev=True).db.name == "from-env"

    def should_fall_back_to_defaults(self):
        assert Settings().db.host == "localhost"

    def should_reject_unknown_fields(self):
        with pytest.raises(ValueError):
            Settings(oidc={"issuer": ISSUER})


class TestOneNamePerSetting:
    """Every setting has exactly one environment variable: its section's prefix plus the field."""

    def should_not_read_a_section_through_its_parents_prefix(self, monkeypatch):
        monkeypatch.setenv("ACEX_DB__HOST", "alias")
        assert Settings().db.host == "localhost"

    def should_not_read_a_nested_section_through_its_parents_prefix(self, monkeypatch):
        monkeypatch.setenv("ACEX_CREDENTIALS__ENCRYPTION_KEY", "alias")
        assert Settings().credentials.encryption_key is None

    def should_read_the_declared_name(self, monkeypatch):
        monkeypatch.setenv("ACEX_CREDENTIALS_ENCRYPTION_KEY", "k")
        assert Settings().credentials.encryption_key.get_secret_value() == "k"

    def should_name_every_section_after_its_path(self):
        # settings.credentials.vault.addr must be ACEX_CREDENTIALS_VAULT_ADDR, so a
        # section's declared name has to match where it is mounted.
        def walk(cls, path):
            for field, info in cls.model_fields.items():
                if isinstance(info.annotation, type) and issubclass(info.annotation, Section):
                    yield (*path, field), info.annotation
                    yield from walk(info.annotation, (*path, field))

        for path, section in walk(Settings, ()):
            assert section.model_config["env_prefix"] == f"ACEX_{'_'.join(path).upper()}_", section


class TestInfluxDB:
    def should_be_unconfigured_without_a_url(self):
        assert not Settings().influxdb.is_configured()

    def should_take_the_primary_output_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_INFLUXDB_URL", "http://influx:8086")
        monkeypatch.setenv("ACEX_INFLUXDB_TOKEN", "t")
        [output] = Settings().influxdb.default_outputs
        assert (output.url, output.token) == ("http://influx:8086", "t")

    def should_take_extra_outputs_as_json_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_INFLUXDB_URL", "http://primary")
        monkeypatch.setenv("ACEX_INFLUXDB_EXTRA_OUTPUTS", '[{"url": "http://replica"}]')
        assert [o.url for o in Settings().influxdb.default_outputs] == ["http://primary", "http://replica"]

    def should_take_outputs_from_code(self):
        influxdb = InfluxDBSettings(url="http://primary", extra_outputs=[InfluxDBOutput(url="http://replica")])
        assert [o.url for o in Settings(influxdb=influxdb).influxdb.groups["default"]] == [
            "http://primary",
            "http://replica",
        ]

    def should_redact_secrets(self, monkeypatch):
        monkeypatch.setenv("ACEX_INFLUXDB_URL", "http://influx:8086")
        monkeypatch.setenv("ACEX_INFLUXDB_TOKEN", "secret")
        [output] = Settings().influxdb.redacted()["default"]
        assert "token" not in output
        assert output["token_set"] is True


class TestRabbitMQ:
    def should_be_unconfigured_without_a_host(self):
        assert not Settings().rabbitmq.configured

    def should_build_the_url_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_RABBITMQ_HOST", "rabbitmq")
        monkeypatch.setenv("ACEX_RABBITMQ_USER", "acex")
        monkeypatch.setenv("ACEX_RABBITMQ_PASSWORD", "pw")
        rabbitmq = Settings().rabbitmq
        assert rabbitmq.configured
        assert rabbitmq.url == "amqp://acex:pw@rabbitmq:5672/%2F"

    def should_quote_characters_that_would_break_the_url(self):
        rabbitmq = RabbitMQSettings(host="rabbitmq", user="acex", password="p@ss/w:rd%", vhost="acex")
        assert rabbitmq.url == "amqp://acex:p%40ss%2Fw%3Ard%25@rabbitmq:5672/acex"

    def should_not_show_the_password(self, monkeypatch):
        monkeypatch.setenv("ACEX_RABBITMQ_HOST", "rabbitmq")
        monkeypatch.setenv("ACEX_RABBITMQ_PASSWORD", "pw")
        assert "pw" not in repr(Settings().rabbitmq)


class TestProxyHeaders:
    """Behind the Kubernetes ingress, a ZTP device's address only reaches the
    API through X-Forwarded-For, and only from a proxy that is trusted."""

    def should_trust_only_localhost_unless_told(self):
        assert Settings().server.forwarded_allow_ips is None

    def should_take_the_trusted_proxies_from_env(self, monkeypatch):
        monkeypatch.setenv("ACEX_SERVER_FORWARDED_ALLOW_IPS", "10.244.0.0/16")
        assert Settings().server.forwarded_allow_ips == "10.244.0.0/16"

    @pytest.mark.parametrize("reload", [False, True])
    def should_hand_them_to_uvicorn(self, monkeypatch, reload):
        import acex_api.app

        served = {}
        monkeypatch.setattr(acex_api.app, "create_app", lambda settings: "app")
        monkeypatch.setattr(acex_api.app.uvicorn, "run", lambda app, **kwargs: served.update(kwargs))
        settings = Settings(dev=True, server={"forwarded_allow_ips": "*", "reload": reload})

        acex_api.app.run(settings)

        assert served["proxy_headers"] is True
        assert served["forwarded_allow_ips"] == "*"
