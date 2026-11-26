"""Tests for AI ops settings: environment layout and chain resolution."""

import os
from unittest.mock import patch

import pytest
from acex.ai_ops.config import AIChainLevel, AIOpsSettings, AIProvider


@pytest.fixture(autouse=True)
def _no_ai_env(monkeypatch):
    """AIOpsSettings reads ACEX_AI_OPS_* on construction; start every test from none."""
    for key in list(os.environ):
        if key.startswith("ACEX_AI_OPS_"):
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
            "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://groq",
            "ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY": "gsk_x",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "groq/moonshotai/Kimi-K3",
            "ACEX_AI_OPS_MCP_SERVER_URL": "http://mcp:8000/mcp",
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
            "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY": "gk",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY": "lk",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS": "qwen3:32b, llama3",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "groq/Kimi-K3, local/qwen3:32b",
            "ACEX_AI_OPS_CHAINS__ANALYSIS": "groq/deepseek-r1",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings()
        assert set(s.providers) == {"groq", "local"}
        assert list(s.providers["local"].models) == ["qwen3:32b", "llama3"]
        assert s.providers["groq"].api == "chat_completions"
        chat_chain = [(lvl.provider, lvl.model) for lvl in s.chain_for("chat")]
        assert chat_chain == [("groq", "Kimi-K3"), ("local", "qwen3:32b")]
        analysis_chain = [(lvl.provider, lvl.model) for lvl in s.chain_for("analysis")]
        assert analysis_chain == [("groq", "deepseek-r1")]

    def test_model_list_as_json(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY": "lk",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS": '["qwen3:32b", "llama3"]',
            "ACEX_AI_OPS_CHAINS__DEFAULT": "local/qwen3:32b",
        }
        with patch.dict(os.environ, env, clear=True):
            assert list(AIOpsSettings().providers["local"].models) == ["qwen3:32b", "llama3"]

    def test_old_field_names_fail_loudly(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY": "lk",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__STATIC_MODELS": "qwen3:32b",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "local/qwen3:32b",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="static_models"):
                AIOpsSettings()

    def test_template_url_with_responses_api(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__GW__BASE_URL": "https://gw/{model}/openai/v1/",
            "ACEX_AI_OPS_PROVIDERS__GW__API": "responses",
            "ACEX_AI_OPS_PROVIDERS__GW__API_KEY": "k",
            "ACEX_AI_OPS_PROVIDERS__GW__MODELS": (
                '{"gpt-a": {"reasoning_effort": "low"}, "gpt-b": {"api": "chat_completions"}}'
            ),
            "ACEX_AI_OPS_CHAINS__DEFAULT": "gw/gpt-a",
            "ACEX_AI_OPS_CHAINS__ANALYSIS": '[{"provider": "gw", "model": "gpt-a", "reasoning_effort": "high"}]',
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings()
        gw = s.providers["gw"]
        assert not gw.discoverable
        assert gw.endpoint("gpt-a") == ("https://gw/gpt-a/openai/v1/", "responses")
        assert gw.endpoint("gpt-b") == ("https://gw/gpt-b/openai/v1/", "chat_completions")
        assert gw.models["gpt-a"].reasoning_effort == "low"
        assert s.chain_for("analysis")[0].reasoning_effort == "high"

    def test_template_url_needs_its_models(self):
        with pytest.raises(ValueError, match="configure its models"):
            AIProvider(base_url="https://gw/{model}/v1", api_key="k")

    def test_model_base_url_override(self):
        provider = AIProvider(base_url="http://a", api_key="k", models={"m": {"base_url": "http://b"}})
        assert provider.endpoint("m") == ("http://b", "chat_completions")
        assert provider.endpoint("other") == ("http://a", "chat_completions")

    def test_chain_referencing_unknown_provider_raises(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY": "k",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "ghost/model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="unknown provider"):
                AIOpsSettings()

    def test_invalid_chain_level_format_raises(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY": "k",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "just-a-model",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="provider/model"):
                AIOpsSettings()

    def test_model_settings_from_env(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__LOCAL__BASE_URL": "http://l",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__API_KEY": "k",
            "ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS": (
                '{"qwen3:32b": {"supports_tools": true, "context_window": 32768, "params": {"temperature": 0.2}}}'
            ),
            "ACEX_AI_OPS_CHAINS__DEFAULT": "local/qwen3:32b",
        }
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings()
        model = s.providers["local"].models["qwen3:32b"]
        assert model.supports_tools is True
        assert model.context_window == 32768
        assert model.params == {"temperature": 0.2}

    def test_providers_without_default_chain_raise(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY": "k",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="ACEX_AI_OPS_CHAINS__DEFAULT"):
                AIOpsSettings()

    def test_provider_without_credentials_raises(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL": "http://g",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "groq/m",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="api_key"):
                AIOpsSettings()

    def test_azure_client_secret_auth_from_env(self):
        env = {
            "ACEX_AI_OPS_PROVIDERS__AZURE__BASE_URL": "https://apim/gpt/openai/v1/",
            "ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__TYPE": "azure_client_secret",
            "ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__TENANT_ID": "t",
            "ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__CLIENT_ID": "c",
            "ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__CLIENT_SECRET": "s",
            "ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__SCOPE": "https://cognitiveservices.azure.com/.default",
            "ACEX_AI_OPS_CHAINS__DEFAULT": "azure/gpt",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = AIOpsSettings().providers["azure"]
        assert provider.api_key is None
        assert (provider.auth.tenant_id, provider.auth.client_id, provider.auth.client_secret) == ("t", "c", "s")
        assert provider.auth.scope == "https://cognitiveservices.azure.com/.default"

    def test_provider_with_both_api_key_and_auth_raises(self):
        auth = {"type": "azure_client_secret", "tenant_id": "t", "client_id": "c", "client_secret": "s", "scope": "x"}
        with pytest.raises(ValueError, match="exactly one of api_key or auth"):
            AIProvider(base_url="http://a", api_key="k", auth=auth)

    def test_unknown_auth_type_raises(self):
        auth = {"type": "basic", "tenant_id": "t", "client_id": "c", "client_secret": "s", "scope": "x"}
        with pytest.raises(ValueError, match="azure_client_secret"):
            AIProvider(base_url="http://a", auth=auth)

    def test_code_fills_in_from_env(self):
        env = {"ACEX_AI_OPS_MCP_SERVER_URL": "http://mcp:8000/mcp"}
        with patch.dict(os.environ, env, clear=True):
            s = AIOpsSettings(
                providers={"groq": {"base_url": "http://g", "api_key": "k"}},
                chains={"default": "groq/m"},
            )
        assert s.mcp_server_url == "http://mcp:8000/mcp"
        assert s.providers["groq"].name == "groq"

    def test_the_old_provider_list_fails_with_a_pointer_to_the_new_layout(self):
        with patch.dict(os.environ, {"ACEX_AI_OPS_PROVIDERS": "groq,local"}, clear=True):
            with pytest.raises(ValueError, match="ACEX_AI_OPS_PROVIDERS__<KEY>__<FIELD>"):
                AIOpsSettings()
