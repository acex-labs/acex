"""AI Ops enabled purely from ACEX_AI_OPS_* env vars, without calling ai_ops() in app.py."""

import os

import pytest
from acex.automation_engine.automationengine import AutomationEngine
from acex.database import Connection
from acex.settings import Settings
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

ENV_MINIMAL = {
    "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://g",
    "ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY": "gk",
    "ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL": "http://l",
    "ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY": "lk",
    "ACEX_AI_OPS_PROVIDERS__LOCAL__STATIC_MODELS": "qwen3:32b",
    "ACEX_AI_OPS_CHAINS__DEFAULT": "groq/Kimi-K3, local/qwen3:32b",
    "ACEX_AI_OPS_CHAINS__ANALYSIS": "groq/deepseek-r1",
    "ACEX_AI_OPS_MCP_SERVER_URL": "http://localhost:8000/mcp",
}


def _engine():
    # dev_mode: these tests exercise AI ops routing, not auth, and an engine
    # without an OIDC issuer otherwise refuses to answer requests.
    return AutomationEngine(db_connection=Connection(), settings=Settings(dev=True))


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Fresh env + writable cwd (sqlite db is created in cwd)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACEX_CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for key in list(os.environ):
        if key.startswith("ACEX_AI_OPS_"):
            monkeypatch.delenv(key)
    yield


def _ai_ops_routes(app):
    # In newer FastAPI, include_router wraps routers as _IncludedRouter objects
    # (no .path attribute); traverse original_router.routes to find APIRoute paths.
    def _collect(routes):
        for r in routes:
            if hasattr(r, "path"):
                yield r.path
            else:
                orig = getattr(r, "original_router", None)
                if orig:
                    yield from _collect(orig.routes)

    return sorted({p for p in _collect(app.routes) if "ai_ops" in p})


class TestEnvOnlyConfiguration:
    def test_no_ai_ops_call_needed(self, monkeypatch):
        """ACEX_AI_OPS_* env vars alone mount the AI ops routes; app.py needs no ai_ops() call."""
        for key, value in ENV_MINIMAL.items():
            monkeypatch.setenv(key, value)

        ae = _engine()
        app = ae.create_app()

        assert isinstance(ae.ai_ops_manager.settings.mcp_server_url, str)
        assert _ai_ops_routes(app) == [
            "/api/v1/ai_ops/ai/ask",
            "/api/v1/ai_ops/ai/config_analysis",
            "/api/v1/ai_ops/models",
            "/api/v1/ai_ops/providers",
        ]

        # Frontend probe + chain overview work
        client = TestClient(app)
        assert client.head("/api/v1/ai_ops/ai/ask").status_code == 200
        body = client.get("/api/v1/ai_ops/providers").json()
        assert {p["name"] for p in body["providers"]} == {"groq", "local"}
        assert body["chains"]["analysis"] == [{"provider": "groq", "model": "deepseek-r1"}]

    def test_no_env_means_no_ai_ops(self):
        """Without ACEX_AI_OPS_* nothing is auto-enabled (router returns None)."""
        ae = _engine()
        app = ae.create_app()
        assert not hasattr(ae, "ai_ops_manager")
        assert _ai_ops_routes(app) == []

    def test_partial_env_raises_clear_error(self, monkeypatch):
        """Providers set but no default chain -> fail at startup with an actionable message."""
        monkeypatch.setenv("ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL", "http://g")
        monkeypatch.setenv("ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY", "gk")
        with pytest.raises(ValueError, match="ACEX_AI_OPS_CHAINS__DEFAULT"):
            _engine().create_app()

    def test_code_config_wins_over_env(self, monkeypatch):
        """An explicit ai_ops() call overrides whatever env vars say."""
        for key, value in {
            **ENV_MINIMAL,
            "ACEX_AI_OPS_CHAINS__DEFAULT": "groq/wrong-env-model",
            "ACEX_AI_OPS_CHAINS__ANALYSIS": "groq/wrong-env-model",
        }.items():
            monkeypatch.setenv(key, value)

        ae = _engine()
        ae.ai_ops(
            enabled=True,
            providers=[{"name": "groq", "base_url": "http://g", "api_key": "gk"}],
            chains={"default": ["groq/code-model"]},
        )
        ae.create_app()
        assert [(lvl.provider, lvl.model) for lvl in ae.ai_ops_manager.settings.chain_for("chat")] == [
            ("groq", "code-model")
        ]

    def test_mcp_server_url_env_used_when_arg_omitted(self, monkeypatch):
        """Code path: mcp_server_url arg omitted falls back to ACEX_AI_OPS_MCP_SERVER_URL."""
        for key, value in ENV_MINIMAL.items():
            monkeypatch.setenv(key, value)

        ae = _engine()
        ae.ai_ops(
            enabled=True,
            providers=[{"name": "groq", "base_url": "http://g", "api_key": "gk"}],
            chains={"default": ["groq/m"]},
        )
        assert ae.ai_ops_manager.settings.mcp_server_url == "http://localhost:8000/mcp"
