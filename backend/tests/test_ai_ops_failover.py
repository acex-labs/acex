"""Tests for AIOpsManager failover logic and model listing cache."""

import json
from unittest.mock import AsyncMock, MagicMock

import mcp.types as mt
import pytest
from acex.ai_ops.ai_ops import (
    ANALYSIS_LOCAL_TOOLS,
    CHAT_LOCAL_TOOLS,
    LOCAL_TOOLS,
    AIOpsManager,
    AllLevelsExhaustedError,
    PlanEvent,
    UsageEvent,
    _hold_partial_marker,
)
from acex.ai_ops.config import AIChainLevel, AIOpsSettings, AIProvider
from openai import APIConnectionError, APIStatusError, APITimeoutError

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _manager():
    settings = AIOpsSettings(
        providers={
            "p1": AIProvider(name="p1", base_url="http://1", api_key="k"),
            "p2": AIProvider(name="p2", base_url="http://2", api_key="k"),
        },
        chains={"default": [AIChainLevel(provider="p1", model="m1"), AIChainLevel(provider="p2", model="m2")]},
        mcp_server_url="http://localhost:8000/mcp",
    )
    manager = AIOpsManager(settings=settings)
    c1, c2 = AsyncMock(), AsyncMock()
    manager._clients = {"p1": c1, "p2": c2}
    return manager, c1, c2


def _conn_error():
    return APIConnectionError(request=MagicMock())


def _status_error(code):
    resp = MagicMock()
    resp.status_code = code
    return APIStatusError("err", response=resp, body=None)


def _ok_response():
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(tool_calls=None))]
    return resp


def _stream(n=2):
    async def gen():
        for i in range(n):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=f"c{i}"))]
            yield chunk

    return gen()


class TestCreateFailover:
    async def test_first_level_success(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(return_value=_ok_response())
        resp, level = await m._create_with_failover("chat", None, messages=[])
        assert level.provider == "p1"
        c2.chat.completions.create.assert_not_called()

    async def test_connection_error_fails_over(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_conn_error())
        c2.chat.completions.create = AsyncMock(return_value=_ok_response())
        resp, level = await m._create_with_failover("chat", None, messages=[])
        assert (level.provider, level.model) == ("p2", "m2")

    async def test_timeout_fails_over(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=MagicMock()))
        c2.chat.completions.create = AsyncMock(return_value=_ok_response())
        _, level = await m._create_with_failover("chat", None, messages=[])
        assert level.provider == "p2"

    @pytest.mark.parametrize("code", [429, 500, 502, 503])
    async def test_retryable_status_codes_fail_over(self, code):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_status_error(code))
        c2.chat.completions.create = AsyncMock(return_value=_ok_response())
        _, level = await m._create_with_failover("chat", None, messages=[])
        assert level.provider == "p2"

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    async def test_client_errors_do_not_fail_over(self, code):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_status_error(code))
        with pytest.raises(APIStatusError):
            await m._create_with_failover("chat", None, messages=[])
        c2.chat.completions.create.assert_not_called()

    async def test_all_levels_exhausted(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_conn_error())
        c2.chat.completions.create = AsyncMock(side_effect=_conn_error())
        with pytest.raises(AllLevelsExhaustedError) as exc_info:
            await m._create_with_failover("chat", None, messages=[])
        assert len(exc_info.value.failures) == 2
        assert "p1/m1" in str(exc_info.value)
        assert "p2/m2" in str(exc_info.value)


class TestModelOverride:
    async def test_unqualified_override_uses_first_chain_provider(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(return_value=_ok_response())
        _, level = await m._create_with_failover("chat", "custom-model", messages=[])
        assert (level.provider, level.model) == ("p1", "custom-model")
        c1.chat.completions.create.assert_called_once()
        assert c1.chat.completions.create.call_args.kwargs["model"] == "custom-model"

    async def test_qualified_override_selects_provider(self):
        m, c1, c2 = _manager()
        c2.chat.completions.create = AsyncMock(return_value=_ok_response())
        _, level = await m._create_with_failover("chat", "p2/other", messages=[])
        assert (level.provider, level.model) == ("p2", "other")
        c1.chat.completions.create.assert_not_called()

    async def test_override_has_no_failover(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_conn_error())
        with pytest.raises(APIConnectionError):
            await m._create_with_failover("chat", "p1/m1", messages=[])
        c2.chat.completions.create.assert_not_called()

    async def test_override_unknown_provider_raises(self):
        m, _, _ = _manager()
        with pytest.raises(ValueError, match="unknown provider"):
            await m._create_with_failover("chat", "ghost/m", messages=[])


class TestStreamFailover:
    async def test_stream_failover_before_first_chunk(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_conn_error())
        c2.chat.completions.create = AsyncMock(return_value=_stream(3))
        chunks = [c async for c in m._stream_with_failover("chat", None, messages=[])]
        assert len(chunks) == 3

    async def test_stream_error_after_first_chunk_does_not_fail_over(self):
        m, c1, c2 = _manager()

        async def broken_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="c0"))]
            yield chunk
            raise APIConnectionError(request=MagicMock())

        c1.chat.completions.create = AsyncMock(return_value=broken_stream())
        c2.chat.completions.create = AsyncMock(return_value=_stream(2))

        chunks = []
        with pytest.raises(AllLevelsExhaustedError):
            async for c in m._stream_with_failover("chat", None, messages=[]):
                chunks.append(c)
        assert len(chunks) == 1  # got one chunk, then stream broke — no restart

    async def test_stream_4xx_raises_immediately(self):
        m, c1, c2 = _manager()
        c1.chat.completions.create = AsyncMock(side_effect=_status_error(401))
        with pytest.raises(APIStatusError):
            async for _ in m._stream_with_failover("chat", None, messages=[]):
                pass
        c2.chat.completions.create.assert_not_called()


class TestUsage:
    def _usage_chunk(self, prompt, completion):
        chunk = MagicMock()
        chunk.choices = []
        chunk.usage = MagicMock(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion)
        return chunk

    @staticmethod
    def _usage_of(chunks):
        """The usage carried by a stream, if any.

        Usage travels as a trailing UsageEvent rather than as manager state:
        the manager is a process-wide singleton, so instance state let
        concurrent users overwrite each other's token counts.
        """
        events = [c for c in chunks if isinstance(c, UsageEvent)]
        return events[-1].data if events else None

    async def test_usage_arrives_as_a_trailing_event(self):
        m, c1, _ = _manager()

        async def stream():
            content = MagicMock()
            content.choices = [MagicMock(delta=MagicMock(content="hi"))]
            yield content
            yield self._usage_chunk(100, 20)

        c1.chat.completions.create = AsyncMock(return_value=stream())
        chunks = [c async for c in m._stream_with_failover("chat", None, messages=[])]
        # one content chunk, then the usage event — never the raw usage chunk
        assert len(chunks) == 2
        assert not isinstance(chunks[0], UsageEvent)
        assert isinstance(chunks[-1], UsageEvent)
        u = self._usage_of(chunks)
        assert u["prompt_tokens"] == 100
        assert u["completion_tokens"] == 20
        assert u["total_tokens"] == 120
        assert u["provider"] == "p1" and u["model"] == "m1"
        assert u["tokens_per_second"] is not None
        assert u["elapsed_seconds"] is not None

    async def test_cost_computed_from_cached_pricing(self):
        m, c1, _ = _manager()
        # Prime pricing cache: 1.0/2.0 USD per MTok
        m._models_cache["p1"] = (
            9999999999,
            [
                {
                    "id": "m1",
                    "is_chat_model": True,
                    "input_cost_per_mtok": 1.0,
                    "output_cost_per_mtok": 2.0,
                    "currency": "USD",
                }
            ],
        )

        async def stream():
            yield self._usage_chunk(1_000_000, 500_000)  # 1M in, 0.5M out

        c1.chat.completions.create = AsyncMock(return_value=stream())
        usage = self._usage_of([c async for c in m._stream_with_failover("chat", None, messages=[])])
        # 1*1.0 + 0.5*2.0 = 2.0 USD
        assert usage["cost"] == 2.0
        assert usage["currency"] == "USD"

    async def test_no_pricing_means_no_cost(self):
        m, c1, _ = _manager()

        async def stream():
            yield self._usage_chunk(100, 20)

        c1.chat.completions.create = AsyncMock(return_value=stream())
        usage = self._usage_of([c async for c in m._stream_with_failover("chat", None, messages=[])])
        assert usage["cost"] is None
        assert usage["currency"] is None

    async def test_no_usage_event_when_provider_reports_none(self):
        m, c1, _ = _manager()

        async def plain_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="x"))]
            yield chunk

        c1.chat.completions.create = AsyncMock(return_value=plain_stream())
        chunks = [c async for c in m._stream_with_failover("chat", None, messages=[])]
        assert self._usage_of(chunks) is None


class TestTextualToolCalls:
    """Some models write their native tool-call syntax into the content when the
    provider fails to convert it into a structured tool_calls field. Treating
    that as a final answer ends the loop early and streams the raw syntax out."""

    @staticmethod
    def _text_response(content):
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(tool_calls=None, content=content))]
        return resp

    @staticmethod
    def _content_stream(pieces):
        async def gen():
            for piece in pieces:
                chunk = MagicMock()
                chunk.choices = [MagicMock(delta=MagicMock(content=piece))]
                chunk.usage = None
                yield chunk

        return gen()

    async def test_model_is_asked_to_retry_the_call_properly(self):
        m, c1, _ = _manager()
        c1.chat.completions.create = AsyncMock(
            side_effect=[
                self._text_response("<tool_call>get_node<arg_key>node_id</arg_key></tool_call>"),
                self._text_response("Node 2 is a distribution switch."),
                self._content_stream(["Node 2 is a distribution switch."]),
            ]
        )
        chunks = [c async for c in m._run_tool_loop("chat", None, [], [LOCAL_TOOLS["plan"]], None)]
        text = "".join(c for c in chunks if isinstance(c, str))
        assert "tool_call" not in text
        # a correction round happened rather than the loop breaking immediately
        assert c1.chat.completions.create.await_count == 3

    async def test_syntax_never_reaches_the_user(self):
        m, c1, _ = _manager()
        c1.chat.completions.create = AsyncMock(
            side_effect=[
                self._text_response("Here you go."),
                self._content_stream(["The answer. ", "<tool_call>get_node</tool_call>", " trailing"]),
            ]
        )
        chunks = [c async for c in m._run_tool_loop("chat", None, [], [], None)]
        assert "".join(c for c in chunks if isinstance(c, str)) == "The answer. "

    async def test_marker_split_across_chunks_is_still_caught(self):
        m, c1, _ = _manager()
        c1.chat.completions.create = AsyncMock(
            side_effect=[
                self._text_response("Here you go."),
                self._content_stream(["Answer. ", "<tool", "_call>get_node</tool_call>"]),
            ]
        )
        chunks = [c async for c in m._run_tool_loop("chat", None, [], [], None)]
        assert "".join(c for c in chunks if isinstance(c, str)) == "Answer. "

    def test_partial_marker_is_held_back(self):
        assert _hold_partial_marker("hello <tool") == ("hello ", "<tool")
        assert _hold_partial_marker("hello <") == ("hello ", "<")
        assert _hold_partial_marker("hello world") == ("hello world", "")


class TestLocalTools:
    def test_plan_offered_to_both_tasks(self):
        """Working out which lookups a change requires is the substance of an
        impact analysis, so planning is not chat-only."""
        assert "plan" in CHAT_LOCAL_TOOLS
        assert "plan" in ANALYSIS_LOCAL_TOOLS

    def test_navigate_is_chat_only(self):
        """navigate_to shows a link in the web UI — meaningless in an analysis."""
        assert "navigate_to" in CHAT_LOCAL_TOOLS
        assert "navigate_to" not in ANALYSIS_LOCAL_TOOLS

    def test_every_offered_tool_is_defined(self):
        for name in set(CHAT_LOCAL_TOOLS) | set(ANALYSIS_LOCAL_TOOLS):
            assert name in LOCAL_TOOLS, f"{name} is offered but has no definition"

    async def test_plan_call_becomes_an_event_and_is_not_forwarded(self):
        """A plan is handled locally; forwarding it to MCP would fail, and the
        steps must reach the UI as an event rather than as prose."""
        m, c1, _ = _manager()
        steps = [{"description": "Find neighbours on Gi1/0/2", "tool": "get_neighbors"}]

        planning = MagicMock()
        planning.choices = [
            MagicMock(
                message=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id="c1",
                            function=MagicMock(
                                name="plan", arguments=json.dumps({"goal": "Assess impact", "steps": steps})
                            ),
                        )
                    ]
                )
            )
        ]
        # MagicMock(name=...) sets the mock's repr, not the attribute
        planning.choices[0].message.tool_calls[0].function.name = "plan"

        async def stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="done"))]
            chunk.usage = None
            yield chunk

        answer = MagicMock()
        answer.choices = [MagicMock(message=MagicMock(tool_calls=None))]
        c1.chat.completions.create = AsyncMock(side_effect=[planning, answer, stream()])

        # mcp=None: a plan must not need the tool server
        chunks = [c async for c in m._run_tool_loop("chat", None, [], [LOCAL_TOOLS["plan"]], None)]

        plans = [c for c in chunks if isinstance(c, PlanEvent)]
        assert len(plans) == 1
        assert plans[0].goal == "Assess impact"
        assert plans[0].steps == steps


class TestToolConversion:
    async def test_input_schema_reaches_the_model(self):
        """MCP puts the schema in `inputSchema`, OpenAI expects `parameters`.

        Reading the wrong field does not raise — it advertises every tool as
        taking no arguments, so the model cannot pass any and some models write
        the call into their reply as text instead.
        """
        m, _, _ = _manager()
        schema = {
            "type": "object",
            "properties": {"node_id": {"type": "integer"}},
            "required": ["node_id"],
        }
        tool = mt.Tool(name="get_node", description="Get one node.", inputSchema=schema)

        converted = m._convert_tools([tool])

        assert converted[0]["function"]["parameters"] == schema
        assert converted[0]["function"]["name"] == "get_node"
        assert converted[0]["function"]["description"] == "Get one node."


class TestMaxTokens:
    """`max_tokens=None` means "no limit", and must be omitted from the request.

    The OpenAI SDK serializes an explicit None as `"max_tokens": null`, which
    strict providers reject with a 400 instead of reading it as unlimited.
    """

    @staticmethod
    async def _run(manager, client, max_tokens):
        async def stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="hi"))]
            chunk.usage = None
            yield chunk

        answer = MagicMock()
        answer.choices = [MagicMock(message=MagicMock(tool_calls=None))]
        client.chat.completions.create = AsyncMock(side_effect=[answer, stream()])
        async for _ in manager._run_tool_loop("chat", None, [], [], None, max_tokens=max_tokens):
            pass
        return client.chat.completions.create.call_args_list

    async def test_omitted_when_unlimited(self):
        m, c1, _ = _manager()
        for call in await self._run(m, c1, None):
            assert "max_tokens" not in call.kwargs

    async def test_sent_when_set(self):
        m, c1, _ = _manager()
        for call in await self._run(m, c1, 4096):
            assert call.kwargs["max_tokens"] == 4096


class TestListModels:
    async def test_live_listing(self):
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [
            MagicMock(id="b", model_dump=lambda: {"id": "b"}),
            MagicMock(id="a", model_dump=lambda: {"id": "a"}),
        ]
        c1.models.list = AsyncMock(return_value=result)
        models = await m.list_models("p1")
        assert [x["id"] for x in models] == ["a", "b"]

    async def test_falls_back_to_static_models(self):
        m, c1, _ = _manager()
        m.settings.providers["p1"].static_models = ["s1", "s2"]
        c1.models.list = AsyncMock(side_effect=_conn_error())
        models = await m.list_models("p1")
        assert [x["id"] for x in models] == ["s1", "s2"]

    async def test_unreachable_without_static_returns_none(self):
        m, c1, _ = _manager()
        c1.models.list = AsyncMock(side_effect=_conn_error())
        assert await m.list_models("p1") is None

    async def test_cache_hit_avoids_second_call(self):
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [MagicMock(id="a", model_dump=lambda: {"id": "a"})]
        c1.models.list = AsyncMock(return_value=result)
        await m.list_models("p1")
        await m.list_models("p1")
        c1.models.list.assert_called_once()

    async def test_force_refresh_bypasses_cache(self):
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [MagicMock(id="a", model_dump=lambda: {"id": "a"})]
        c1.models.list = AsyncMock(return_value=result)
        await m.list_models("p1")
        await m.list_models("p1", force_refresh=True)
        assert c1.models.list.call_count == 2

    async def test_unknown_provider_raises(self):
        m, _, _ = _manager()
        with pytest.raises(ValueError, match="Unknown provider"):
            await m.list_models("ghost")


class TestModelMetadata:
    def _mock_model(self, dump):
        mock = MagicMock()
        mock.id = dump["id"]
        mock.model_dump = lambda: dump
        return mock

    async def test_harvests_openrouter_style_fields(self):
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [
            self._mock_model(
                {
                    "id": "vendor/model",
                    "created": 123,
                    "owned_by": "vendor",
                    "context_length": 131072,
                    "capabilities": {"tools": True, "vision": False},
                    "pricing": {"prompt": "0.0000008", "completion": "0.000002"},
                    "some_vendor_field": "kept-in-extra",
                }
            )
        ]
        c1.models.list = AsyncMock(return_value=result)
        models = await m.list_models("p1")
        (entry,) = models
        assert entry["id"] == "vendor/model"
        assert entry["supports_tools"] is True
        assert entry["supports_vision"] is False
        assert entry["context_window"] == 131072
        assert entry["input_cost_per_mtok"] == 0.8
        assert entry["output_cost_per_mtok"] == 2.0
        assert entry["currency"] == "USD"
        assert entry["extra"] == {"some_vendor_field": "kept-in-extra"}

    async def test_harvests_berget_style_fields(self):
        """Real Berget /models payload: pricing already per-MTok with currency,
        capabilities.function_calling/vision, plus status.up/latency in extra."""
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [
            self._mock_model(
                {
                    "id": "moonshotai/Kimi-K3",
                    "object": "model",
                    "created": 1785196800000,
                    "owned_by": "moonshotai",
                    "name": "Kimi-K3",
                    "pricing": {"currency": "EUR", "input": 3, "output": 15, "unit": "€ / M Token"},
                    "capabilities": {
                        "classification": False,
                        "embeddings": False,
                        "formatted_output": True,
                        "function_calling": True,
                        "json_mode": True,
                        "streaming": True,
                        "vision": True,
                    },
                    "status": {"up": True, "latency": 1657},
                    "lifecycle_state": "eval",
                }
            )
        ]
        c1.models.list = AsyncMock(return_value=result)
        (entry,) = await m.list_models("p1")
        assert entry["supports_tools"] is True
        assert entry["supports_vision"] is True
        assert entry["input_cost_per_mtok"] == 3
        assert entry["output_cost_per_mtok"] == 15
        assert entry["currency"] == "EUR"
        assert entry["extra"]["status"] == {"up": True, "latency": 1657}
        assert entry["extra"]["lifecycle_state"] == "eval"

    async def test_harvests_openrouter_style_fields_full(self):
        """Real OpenRouter payload: per-token pricing strings, supported_parameters
        for tools, architecture.input_modalities for vision, context_length."""
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [
            self._mock_model(
                {
                    "id": "qwen/qwen3.8-27b",
                    "name": "Qwen: Qwen3.8 27B",
                    "created": 1786722910,
                    "context_length": 262144,
                    "architecture": {
                        "modality": "text+image+video->text",
                        "input_modalities": ["text", "image", "video"],
                    },
                    "pricing": {"prompt": "0.00000045", "completion": "0.0000032"},
                    "supported_parameters": ["temperature", "tools", "tool_choice"],
                    "description": "...",
                }
            )
        ]
        c1.models.list = AsyncMock(return_value=result)
        (entry,) = await m.list_models("p1")
        assert entry["supports_tools"] is True
        assert entry["supports_vision"] is True
        assert entry["context_window"] == 262144
        assert entry["input_cost_per_mtok"] == 0.45
        assert entry["output_cost_per_mtok"] == 3.2
        assert entry["currency"] == "USD"

    async def test_bare_openai_spec_model_has_null_metadata(self):
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [self._mock_model({"id": "plain", "created": 1, "object": "model", "owned_by": "x"})]
        c1.models.list = AsyncMock(return_value=result)
        (entry,) = await m.list_models("p1")
        assert entry["id"] == "plain"
        assert entry["supports_tools"] is None
        assert entry["context_window"] is None
        assert entry["input_cost_per_mtok"] is None
        assert entry["extra"] is None

    async def test_config_override_wins(self):
        from acex.ai_ops.config import AIModelMeta

        m, c1, _ = _manager()
        m.settings.providers["p1"].model_meta = {
            "plain": AIModelMeta(supports_tools=True, context_window=32768, input_cost_per_mtok=0.0)
        }
        result = MagicMock()
        result.data = [self._mock_model({"id": "plain", "capabilities": {"tools": False}})]
        c1.models.list = AsyncMock(return_value=result)
        (entry,) = await m.list_models("p1")
        assert entry["supports_tools"] is True  # override beats harvested False
        assert entry["context_window"] == 32768
        assert entry["input_cost_per_mtok"] == 0.0

    async def test_override_merges_extra(self):
        from acex.ai_ops.config import AIModelMeta

        m, c1, _ = _manager()
        m.settings.providers["p1"].model_meta = {"m": AIModelMeta(extra={"family": "test"})}
        result = MagicMock()
        result.data = [self._mock_model({"id": "m", "vendor_field": 1})]
        c1.models.list = AsyncMock(return_value=result)
        (entry,) = await m.list_models("p1")
        assert entry["extra"] == {"vendor_field": 1, "family": "test"}

    async def test_filters_non_chat_models_berget_style(self):
        """Berget marks non-chat models via model_type."""
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [
            self._mock_model({"id": "Kimi-K3", "model_type": "text"}),
            self._mock_model({"id": "kb-whisper-large", "model_type": "speech-to-text"}),
            self._mock_model({"id": "multilingual-e5-large", "model_type": "embedding"}),
            self._mock_model({"id": "bge-reranker-v2-m3", "model_type": "rerank"}),
        ]
        c1.models.list = AsyncMock(return_value=result)

        filtered = await m.list_models("p1")
        assert [x["id"] for x in filtered] == ["Kimi-K3"]

        unfiltered = await m.list_models("p1", include_all=True)
        assert len(unfiltered) == 4
        by_id = {x["id"]: x for x in unfiltered}
        assert by_id["Kimi-K3"]["is_chat_model"] is True
        assert by_id["kb-whisper-large"]["is_chat_model"] is False
        assert by_id["multilingual-e5-large"]["is_chat_model"] is False
        assert by_id["bge-reranker-v2-m3"]["is_chat_model"] is False

    async def test_filters_non_chat_models_openrouter_style(self):
        """OpenRouter marks output modalities via architecture."""
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [
            self._mock_model({"id": "text-model", "architecture": {"output_modalities": ["text"]}}),
            self._mock_model({"id": "image-gen", "architecture": {"output_modalities": ["image", "text"]}}),
            # text+image outputs still produce text — kept
            self._mock_model({"id": "image-only", "architecture": {"output_modalities": ["image"]}}),
        ]
        c1.models.list = AsyncMock(return_value=result)
        filtered = await m.list_models("p1")
        assert [x["id"] for x in filtered] == ["image-gen", "text-model"]

    async def test_unknown_type_assumed_chat(self):
        """Plain OpenAI-spec models (no model_type/architecture) are kept."""
        m, c1, _ = _manager()
        result = MagicMock()
        result.data = [self._mock_model({"id": "plain", "created": 1})]
        c1.models.list = AsyncMock(return_value=result)
        filtered = await m.list_models("p1")
        assert [x["id"] for x in filtered] == ["plain"]
        assert filtered[0]["is_chat_model"] is True

    async def test_static_models_get_override_metadata(self):
        from acex.ai_ops.config import AIModelMeta

        m, c1, _ = _manager()
        m.settings.providers["p1"].static_models = ["local-model"]
        m.settings.providers["p1"].model_meta = {"local-model": AIModelMeta(supports_tools=True)}
        c1.models.list = AsyncMock(side_effect=_conn_error())
        (entry,) = await m.list_models("p1")
        assert entry["id"] == "local-model"
        assert entry["supports_tools"] is True
