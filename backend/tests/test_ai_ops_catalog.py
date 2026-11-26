"""Model catalog: listing, harvested metadata, configured models, cost."""

import pytest
from acex.ai_ops.config import AIModelConfig, AIProvider
from acex.ai_ops.errors import ProviderError
from acex.ai_ops.types import Usage
from ai_ops_fakes import FakeAdapter, manager

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _listing(*dumps):
    return manager(p1=FakeAdapter(models=list(dumps)))


class TestListing:
    async def test_sorted_by_id(self):
        m = _listing({"id": "b"}, {"id": "a"})
        assert [x["id"] for x in await m.list_models("p1")] == ["a", "b"]

    async def test_configured_models_are_listed_with_the_listing(self):
        m = _listing({"id": "a"})
        m.settings.providers["p1"].models = {"local": AIModelConfig(supports_tools=True)}
        models = {x["id"]: x for x in await m.list_models("p1")}
        assert set(models) == {"a", "local"}
        assert models["local"]["supports_tools"] is True

    async def test_unreachable_falls_back_to_configured_models(self):
        m = manager(p1=FakeAdapter(models=ProviderError("down", "transient")))
        m.settings.providers["p1"].models = {"s1": AIModelConfig(), "s2": AIModelConfig()}
        assert [x["id"] for x in await m.list_models("p1")] == ["s1", "s2"]

    async def test_unreachable_without_configured_models_is_none(self):
        m = manager(p1=FakeAdapter(models=ProviderError("down", "transient")))
        assert await m.list_models("p1") is None

    async def test_template_url_is_not_listed(self):
        """A {model} URL has no single /models to ask; the configured models are the list."""
        provider = AIProvider(base_url="https://gw/{model}/v1", api_key="k", models="gpt-a,gpt-b")
        adapter = FakeAdapter(models=ProviderError("must not be called", "invalid_request"))
        m = manager(providers={"gw": provider}, chain=("gw/gpt-a",), gw=adapter)
        assert [x["id"] for x in await m.list_models("gw")] == ["gpt-a", "gpt-b"]

    async def test_cached(self):
        adapter = FakeAdapter(models=[{"id": "a"}])
        m = manager(p1=adapter)
        await m.list_models("p1")
        adapter.models = [{"id": "b"}]
        assert [x["id"] for x in await m.list_models("p1")] == ["a"]
        assert [x["id"] for x in await m.list_models("p1", force_refresh=True)] == ["b"]

    async def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            await manager().list_models("ghost")


class TestHarvest:
    async def test_openrouter_fields(self):
        m = _listing(
            {
                "id": "qwen/qwen3.8-27b",
                "context_length": 262144,
                "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
                "pricing": {"prompt": "0.00000045", "completion": "0.0000032"},
                "supported_parameters": ["temperature", "tools"],
                "description": "kept",
            }
        )
        (entry,) = await m.list_models("p1")
        assert entry["supports_tools"] is True
        assert entry["supports_vision"] is True
        assert entry["context_window"] == 262144
        assert (entry["input_cost_per_mtok"], entry["output_cost_per_mtok"], entry["currency"]) == (0.45, 3.2, "USD")
        assert entry["extra"] == {"description": "kept"}

    async def test_berget_fields(self):
        m = _listing(
            {
                "id": "moonshotai/Kimi-K3",
                "pricing": {"currency": "EUR", "input": 3, "output": 15},
                "capabilities": {"function_calling": True, "vision": True},
                "status": {"up": True},
            }
        )
        (entry,) = await m.list_models("p1")
        assert (entry["supports_tools"], entry["supports_vision"]) == (True, True)
        assert (entry["input_cost_per_mtok"], entry["output_cost_per_mtok"], entry["currency"]) == (3, 15, "EUR")
        assert entry["extra"]["status"] == {"up": True}

    async def test_plain_openai_entry_has_null_metadata(self):
        m = _listing({"id": "plain", "created": 1, "object": "model", "owned_by": "x"})
        (entry,) = await m.list_models("p1")
        assert entry["supports_tools"] is None and entry["context_window"] is None and entry["extra"] is None

    async def test_configuration_wins_and_merges_extra(self):
        m = _listing({"id": "m", "capabilities": {"tools": False}, "vendor": 1})
        m.settings.providers["p1"].models = {
            "m": AIModelConfig(supports_tools=True, context_window=32768, extra={"family": "x"})
        }
        (entry,) = await m.list_models("p1")
        assert entry["supports_tools"] is True
        assert entry["context_window"] == 32768
        assert entry["extra"] == {"vendor": 1, "family": "x"}

    async def test_non_chat_models_are_filtered(self):
        m = _listing(
            {"id": "kimi", "model_type": "text"},
            {"id": "whisper", "model_type": "speech-to-text"},
            {"id": "image-only", "architecture": {"output_modalities": ["image"]}},
            {"id": "plain"},
        )
        assert [x["id"] for x in await m.list_models("p1")] == ["kimi", "plain"]
        assert len(await m.list_models("p1", include_all=True)) == 4


class TestCost:
    async def test_from_listed_pricing(self):
        m = _listing({"id": "m1", "pricing": {"currency": "USD", "input": 1.0, "output": 2.0}})
        await m.list_models("p1")
        usage = Usage(prompt_tokens=1_000_000, completion_tokens=500_000)
        assert m.catalog.cost("p1", "m1", usage) == (2.0, "USD")

    def test_from_configuration_without_a_listing(self):
        m = manager()
        m.settings.providers["p1"].models = {"m1": AIModelConfig(input_cost_per_mtok=1.0, output_cost_per_mtok=1.0)}
        assert m.catalog.cost("p1", "m1", Usage(prompt_tokens=1_000_000))[0] == 1.0

    def test_unknown_pricing_has_no_cost(self):
        assert manager().catalog.cost("p1", "m1", Usage(prompt_tokens=10)) == (None, None)
