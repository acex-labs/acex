"""Tests for AI ops settings parsing (env vars) and chain resolution."""

import os
from unittest.mock import patch

import pytest
from acex.ai_ops.config import AIChainLevel, AIOpsSettings, AIProvider


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
    def test_empty_env_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            assert AIOpsSettings.from_env() is None

    def test_single_provider_minimal(self):
        env = {
            "ACEX_AI_PROVIDERS": "groq",
            "ACEX_AI_PROVIDER_GROQ_BASEURL": "http://groq",
            "ACEX_AI_PROVIDER_GROQ_API_KEY": "gsk_x",
            "ACEX_AI_CHAIN_DEFAULT": "groq/moonshotai/Kimi-K3",
            "ACEX_AI_MCP_SERVER_URL": "http://mcp:8000/mcp",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings.from_env()
        assert list(s.providers) == ["groq"]
        assert s.providers["groq"].base_url == "http://groq"
        assert [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")] == [("groq", "moonshotai/Kimi-K3")]
        assert s.mcp_server_url == "http://mcp:8000/mcp"

    def test_named_providers_and_chains(self):
        env = {
            "ACEX_AI_PROVIDERS": "groq,local",
            "ACEX_AI_PROVIDER_GROQ_BASEURL": "http://g",
            "ACEX_AI_PROVIDER_GROQ_API_KEY": "gk",
            "ACEX_AI_PROVIDER_LOCAL_BASEURL": "http://l",
            "ACEX_AI_PROVIDER_LOCAL_API_KEY": "lk",
            "ACEX_AI_PROVIDER_LOCAL_STATIC_MODELS": "qwen3:32b, llama3",
            "ACEX_AI_CHAIN_DEFAULT": "groq/Kimi-K3, local/qwen3:32b",
            "ACEX_AI_CHAIN_ANALYSIS": "groq/deepseek-r1",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings.from_env()
        assert set(s.providers) == {"groq", "local"}
        assert s.providers["local"].static_models == ["qwen3:32b", "llama3"]
        chat_chain = [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")]
        assert chat_chain == [("groq", "Kimi-K3"), ("local", "qwen3:32b")]
        analysis_chain = [(lvl.provider, lvl.model) for lvl in s.chain_for("analysis")]
        assert analysis_chain == [("groq", "deepseek-r1")]

    def test_chain_referencing_unknown_provider_raises(self):
        env = {
            "ACEX_AI_PROVIDERS": "groq",
            "ACEX_AI_PROVIDER_GROQ_BASEURL": "http://g",
            "ACEX_AI_PROVIDER_GROQ_API_KEY": "k",
            "ACEX_AI_CHAIN_DEFAULT": "ghost/model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="unknown provider"):
                AIOpsSettings.from_env()

    def test_invalid_chain_level_format_raises(self):
        env = {
            "ACEX_AI_PROVIDERS": "groq",
            "ACEX_AI_PROVIDER_GROQ_BASEURL": "http://g",
            "ACEX_AI_PROVIDER_GROQ_API_KEY": "k",
            "ACEX_AI_CHAIN_DEFAULT": "just-a-model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="provider/model"):
                AIOpsSettings.from_env()

    def test_model_meta_from_env(self):
        env = {
            "ACEX_AI_PROVIDERS": "local",
            "ACEX_AI_PROVIDER_LOCAL_BASEURL": "http://l",
            "ACEX_AI_PROVIDER_LOCAL_API_KEY": "k",
            "ACEX_AI_PROVIDER_LOCAL_MODEL_META": '{"qwen3:32b": {"supports_tools": true, "context_window": 32768}}',
            "ACEX_AI_CHAIN_DEFAULT": "local/qwen3:32b",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings.from_env()
        meta = s.providers["local"].model_meta["qwen3:32b"]
        assert meta.supports_tools is True
        assert meta.context_window == 32768

    def test_providers_without_chain_returns_none(self):
        env = {
            "ACEX_AI_PROVIDERS": "groq",
            "ACEX_AI_PROVIDER_GROQ_BASEURL": "http://g",
            "ACEX_AI_PROVIDER_GROQ_API_KEY": "k",
        }
        with patch.dict(os.environ, env, clear=True):
            assert AIOpsSettings.from_env() is None

    def test_provider_without_credentials_skipped(self):
        env = {
            "ACEX_AI_PROVIDERS": "groq,broken",
            "ACEX_AI_PROVIDER_GROQ_BASEURL": "http://g",
            "ACEX_AI_PROVIDER_GROQ_API_KEY": "gk",
            # "broken" has no BASEURL/API_KEY
            "ACEX_AI_CHAIN_DEFAULT": "groq/m",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings.from_env()
        assert set(s.providers) == {"groq"}
