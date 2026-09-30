"""Tests for AI ops settings: environment layout and chain resolution."""

import os
from unittest.mock import patch

import pytest
from acex.ai_ops.config import AIChainLevel, AIOpsSettings, AIProvider


@pytest.fixture(autouse=True)
def _no_ai_env(monkeypatch):
    """AIOpsSettings reads ACEX_AI_* on construction; start every test from none."""
    for key in list(os.environ):
        if key.startswith("ACEX_AI_"):
            monkeypatch.delenv(key)


def _settings(**chain_overrides):
    chains = {"default": [AIChainLevel(provider="p1", model="m1"), AIChainLevel(provider="p2", model="m2")]}
    chains.update(chain_overrides)
    return AIOpsSettings(
        providers={
            "p1": AIProvider(name="p1", base_url="http://1", api_key="k"),
            "p2": AIProvider(name="p2", base_url="http://2", api_key="k"),
        },
        chains=chains,
        mcp_server_url="http://localhost:8000/mcp",
    )


class TestChainResolution:
    def test_task_inherits_default(self):
        s = _settings()
        assert [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")] == [("p1", "m1"), ("p2", "m2")]
        assert [(lvl.provider, lvl.model) for lvl in s.chain_for("analysis")] == [("p1", "m1"), ("p2", "m2")]

    def test_task_specific_chain_overrides_default(self):
        s = _settings(analysis=[AIChainLevel(provider="p2", model="m2")])
        assert [(lvl.provider, lvl.model) for lvl in s.chain_for("analysis")] == [("p2", "m2")]
        # chat untouched
        assert [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")] == [("p1", "m1"), ("p2", "m2")]

    def test_no_chain_raises(self):
        s = AIOpsSettings(providers={}, chains={})
        with pytest.raises(ValueError, match="No AI chain configured"):
            s.chain_for("chat")

    def test_unknown_provider_reference_raises(self):
        s = _settings()
        with pytest.raises(ValueError, match="unknown provider"):
            s.provider_for(AIChainLevel(provider="nope", model="x"))


class TestFromEnv:
    def test_empty_env_means_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            s = AIOpsSettings()
        assert not s.enabled

    def test_single_provider_minimal(self):
        env = {
            "ACEX_AI_PROVIDERS__GROQ__BASE_URL": "http://groq",
            "ACEX_AI_PROVIDERS__GROQ__API_KEY": "gsk_x",
            "ACEX_AI_CHAINS__DEFAULT": "groq/moonshotai/Kimi-K3",
            "ACEX_AI_MCP_SERVER_URL": "http://mcp:8000/mcp",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings()
        assert s.enabled
        assert list(s.providers) == ["groq"]
        assert s.providers["groq"].name == "groq"
        assert s.providers["groq"].base_url == "http://groq"
        assert [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")] == [("groq", "moonshotai/Kimi-K3")]
        assert s.mcp_server_url == "http://mcp:8000/mcp"

    def test_named_providers_and_chains(self):
        env = {
            "ACEX_AI_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_PROVIDERS__GROQ__API_KEY": "gk",
            "ACEX_AI_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_PROVIDERS__LOCAL__API_KEY": "lk",
            "ACEX_AI_PROVIDERS__LOCAL__STATIC_MODELS": "qwen3:32b, llama3",
            "ACEX_AI_CHAINS__DEFAULT": "groq/Kimi-K3, local/qwen3:32b",
            "ACEX_AI_CHAINS__ANALYSIS": "groq/deepseek-r1",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings()
        assert set(s.providers) == {"groq", "local"}
        assert s.providers["local"].static_models == ["qwen3:32b", "llama3"]
        chat_chain = [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")]
        assert chat_chain == [("groq", "Kimi-K3"), ("local", "qwen3:32b")]
        analysis_chain = [(lvl.provider, lvl.model) for lvl in s.chain_for("analysis")]
        assert analysis_chain == [("groq", "deepseek-r1")]

    def test_static_models_as_json(self):
        env = {
            "ACEX_AI_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_PROVIDERS__LOCAL__API_KEY": "lk",
            "ACEX_AI_PROVIDERS__LOCAL__STATIC_MODELS": '["qwen3:32b", "llama3"]',
            "ACEX_AI_CHAINS__DEFAULT": "local/qwen3:32b",
        }
        with patch.dict(os.environ, env, clear=True):
            assert AIOpsSettings().providers["local"].static_models == ["qwen3:32b", "llama3"]

    def test_chain_referencing_unknown_provider_raises(self):
        env = {
            "ACEX_AI_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_PROVIDERS__GROQ__API_KEY": "k",
            "ACEX_AI_CHAINS__DEFAULT": "ghost/model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="unknown provider"):
                AIOpsSettings()

    def test_invalid_chain_level_format_raises(self):
        env = {
            "ACEX_AI_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_PROVIDERS__GROQ__API_KEY": "k",
            "ACEX_AI_CHAINS__DEFAULT": "just-a-model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="provider/model"):
                AIOpsSettings()

    def test_model_meta_from_env(self):
        env = {
            "ACEX_AI_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_PROVIDERS__LOCAL__API_KEY": "k",
            "ACEX_AI_PROVIDERS__LOCAL__MODEL_META": '{"qwen3:32b": {"supports_tools": true, "context_window": 32768}}',
            "ACEX_AI_CHAINS__DEFAULT": "local/qwen3:32b",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings()
        meta = s.providers["local"].model_meta["qwen3:32b"]
        assert meta.supports_tools is True
        assert meta.context_window == 32768

    def test_providers_without_default_chain_raise(self):
        env = {
            "ACEX_AI_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_PROVIDERS__GROQ__API_KEY": "k",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="ACEX_AI_CHAINS__DEFAULT"):
                AIOpsSettings()

    def test_provider_without_credentials_raises(self):
        env = {
            "ACEX_AI_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_CHAINS__DEFAULT": "groq/m",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="api_key"):
                AIOpsSettings()

    def test_code_fills_in_from_env(self):
        env = {"ACEX_AI_MCP_SERVER_URL": "http://mcp:8000/mcp"}
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings(
                providers={"groq": {"base_url": "http://g", "api_key": "k"}},
                chains={"default": "groq/m"},
            )
        assert s.mcp_server_url == "http://mcp:8000/mcp"
        assert s.providers["groq"].name == "groq"

    def test_the_old_provider_list_fails_with_a_pointer_to_the_new_layout(self):
        with patch.dict(os.environ, {"ACEX_AI_PROVIDERS": "groq,local"}, clear=True):
            with pytest.raises(ValueError, match="ACEX_AI_PROVIDERS__<KEY>__<FIELD>"):
                AIOpsSettings()
