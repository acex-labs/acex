"""Model adapters: translation to each wire protocol and back."""

import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from acex.ai_ops.adapters import ChatCompletionsAdapter, ResponsesAdapter
from acex.ai_ops.adapters.openai_sdk import OpenAISDKAdapter
from acex.ai_ops.errors import ProviderError
from acex.ai_ops.types import (
    AssistantRound,
    Message,
    RoundState,
    TextDelta,
    ToolCall,
    ToolResult,
    ToolSpec,
    Turn,
    Usage,
)
from openai import APIConnectionError, APIStatusError, BadRequestError

pytestmark = pytest.mark.anyio

TOOL = ToolSpec("get_node", "Get one node.", {"type": "object", "properties": {"id": {"type": "integer"}}})


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _replay(items):
    for item in items:
        yield item


async def _events(adapter, turn):
    return [event async for event in adapter.stream(turn)]


def _status_error(code, param=None):
    response = httpx.Response(code, request=httpx.Request("POST", "http://x"))
    body = {"message": "nope", "param": param}
    cls = BadRequestError if code == 400 else APIStatusError
    return cls("nope", response=response, body=body)


class TestErrors:
    @pytest.mark.parametrize(
        ("code", "param", "kind"),
        [
            (500, None, "transient"),
            (503, None, "transient"),
            (429, None, "rate_limit"),
            (401, None, "auth"),
            (403, None, "auth"),
            (400, "messages", "invalid_request"),
            (400, "reasoning_effort", "unsupported"),
            (400, "tools", "unsupported"),
        ],
    )
    def test_status_codes_are_classified(self, code, param, kind):
        error = OpenAISDKAdapter.error(_status_error(code, param))
        assert (error.kind, error.status, error.param) == (kind, code, param)

    def test_connection_errors_are_transient(self):
        error = OpenAISDKAdapter.error(APIConnectionError(request=MagicMock()))
        assert error.kind == "transient" and error.failover

    def test_only_transient_kinds_fail_over(self):
        assert ProviderError("x", "rate_limit").failover
        assert not ProviderError("x", "unsupported").failover
        assert not ProviderError("x", "auth").failover


class TestToolCallArguments:
    def test_json_string(self):
        assert OpenAISDKAdapter.tool_call("c", "t", '{"a": 1}').arguments == {"a": 1}

    def test_dict_from_a_lenient_provider(self):
        call = OpenAISDKAdapter.tool_call("c", "t", {"a": 1})
        assert call.arguments == {"a": 1} and call.raw_arguments == '{"a": 1}'

    def test_empty_means_no_arguments(self):
        assert OpenAISDKAdapter.tool_call("c", "t", "").arguments == {}

    @pytest.mark.parametrize("raw", ["{not json", "[1, 2]"])
    def test_anything_but_an_object_is_none(self, raw):
        call = OpenAISDKAdapter.tool_call("c", "t", raw)
        assert call.arguments is None and call.raw_arguments == raw


class TestChatCompletions:
    @staticmethod
    def _adapter(chunks=()):
        adapter = ChatCompletionsAdapter("http://x", "k")
        adapter.client = MagicMock()
        adapter.client.chat.completions.create = AsyncMock(return_value=_replay(chunks))
        return adapter

    @staticmethod
    def _chunk(content=None, tool_calls=None, usage=None, delta=True):
        choice = NS(delta=NS(content=content, tool_calls=tool_calls) if delta else None)
        return NS(choices=[choice] if (content or tool_calls or not delta) else [], usage=usage)

    @staticmethod
    def _part(index, id=None, name=None, arguments=None):
        return NS(index=index, id=id, function=NS(name=name, arguments=arguments))

    async def test_text_then_assembled_tool_calls_then_usage(self):
        adapter = self._adapter(
            [
                self._chunk("Let me "),
                self._chunk("check."),
                self._chunk(tool_calls=[self._part(0, "c1", "get_node", '{"id"')]),
                self._chunk(tool_calls=[self._part(0, arguments=": 7}")]),
                self._chunk(tool_calls=[self._part(1, "c2", "plan", "{}")]),
                self._chunk(usage=NS(prompt_tokens=10, completion_tokens=5)),
            ]
        )
        events = await _events(adapter, Turn(model="m", conversation=[]))
        assert events[:2] == [TextDelta("Let me "), TextDelta("check.")]
        assert [(c.id, c.name, c.arguments) for c in events[2:4]] == [("c1", "get_node", {"id": 7}), ("c2", "plan", {})]
        assert events[4] == Usage(prompt_tokens=10, completion_tokens=5)

    async def test_choice_without_delta_is_skipped(self):
        """Azure sends choices without a delta, e.g. for content-filter results."""
        adapter = self._adapter([self._chunk(delta=False), self._chunk("hi")])
        assert await _events(adapter, Turn(model="m", conversation=[])) == [TextDelta("hi")]

    async def test_reasoning_and_extras_in_usage(self):
        usage = NS(
            prompt_tokens=10,
            completion_tokens=5,
            completion_tokens_details=NS(reasoning_tokens=3),
            prompt_tokens_details={"cached_tokens": 4},
            co2_grams=0.5,
        )
        adapter = self._adapter([self._chunk(usage=usage)])
        (result,) = await _events(adapter, Turn(model="m", conversation=[]))
        assert (result.reasoning_tokens, result.cached_tokens, result.co2_grams) == (3, 4, 0.5)

    async def test_sdk_errors_become_provider_errors(self):
        adapter = self._adapter()
        adapter.client.chat.completions.create = AsyncMock(side_effect=_status_error(400, "reasoning_effort"))
        with pytest.raises(ProviderError) as raised:
            await _events(adapter, Turn(model="m", conversation=[]))
        assert raised.value.kind == "unsupported"

    def test_request(self):
        turn = Turn(
            model="m",
            conversation=[Message("user", "hi")],
            tools=[TOOL],
            tool_choice="none",
            max_tokens=99,
            reasoning_effort="low",
            params={"temperature": 0.1, "max_tokens": 10},
        )
        request = ChatCompletionsAdapter("http://x", "k").request(turn)
        assert request["tools"] == [
            {
                "type": "function",
                "function": {"name": "get_node", "description": "Get one node.", "parameters": TOOL.parameters},
            }
        ]
        assert request["tool_choice"] == "none"
        assert request["reasoning_effort"] == "low"
        assert request["temperature"] == 0.1
        assert request["max_tokens"] == 10  # params win
        assert request["stream_options"] == {"include_usage": True}

    def test_unset_fields_are_left_out(self):
        """The SDK serializes None as null, which strict providers reject."""
        request = ChatCompletionsAdapter("http://x", "k").request(Turn(model="m", conversation=[]))
        assert not {"tools", "tool_choice", "max_tokens", "reasoning_effort"} & set(request)

    def test_conversation(self):
        call = ToolCall("c1", "get_node", {"id": 7})
        messages = ChatCompletionsAdapter.messages(
            [
                Message("system", "be brief"),
                Message("user", "hi"),
                AssistantRound("Checking.", [call], state=["ignored"]),
                ToolResult("c1", "get_node", '{"ok": true}'),
            ]
        )
        assert messages == [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "Checking.",
                "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_node", "arguments": '{"id": 7}'}}
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "name": "get_node", "content": '{"ok": true}'},
        ]


class TestResponses:
    @staticmethod
    def _adapter(events=()):
        adapter = ResponsesAdapter("http://x", "k")
        adapter.client = MagicMock()
        adapter.client.responses.create = AsyncMock(return_value=_replay(events))
        return adapter

    @staticmethod
    def _item(**fields):
        item = NS(**fields)
        item.model_dump = MagicMock(return_value=dict(fields))
        return item

    async def test_text_tool_calls_state_and_usage(self):
        reasoning = self._item(type="reasoning", id="rs_1", encrypted_content="xyz")
        call = self._item(type="function_call", id="fc_1", call_id="c1", name="get_node", arguments='{"id": 7}')
        usage = NS(
            input_tokens=10,
            output_tokens=5,
            output_tokens_details=NS(reasoning_tokens=3),
            input_tokens_details=NS(cached_tokens=2),
        )
        adapter = self._adapter(
            [
                NS(type="response.output_item.done", item=reasoning),
                NS(type="response.output_text.delta", delta="Checking."),
                NS(type="response.output_item.done", item=call),
                NS(type="response.completed", response=NS(usage=usage)),
            ]
        )
        events = await _events(adapter, Turn(model="m", conversation=[]))
        assert events[0] == TextDelta("Checking.")
        assert (events[1].id, events[1].name, events[1].arguments) == ("c1", "get_node", {"id": 7})
        assert events[2] == RoundState([reasoning.model_dump.return_value, call.model_dump.return_value]), (
            "every output item, in order, to send back verbatim"
        )
        assert events[3] == Usage(prompt_tokens=10, completion_tokens=5, reasoning_tokens=3, cached_tokens=2)

    @pytest.mark.parametrize(
        ("code", "kind"),
        [("rate_limit_exceeded", "rate_limit"), ("server_error", "transient"), ("bad", "invalid_request")],
    )
    async def test_failure_in_the_stream(self, code, kind):
        adapter = self._adapter([NS(type="response.failed", response=NS(error=NS(code=code, message="m", param=None)))])
        with pytest.raises(ProviderError) as raised:
            await _events(adapter, Turn(model="m", conversation=[]))
        assert raised.value.kind == kind

    def test_request(self):
        turn = Turn(model="m", conversation=[], tools=[TOOL], max_tokens=99, reasoning_effort="high")
        request = ResponsesAdapter("http://x", "k").request(turn)
        assert request["tools"] == [
            {
                "type": "function",
                "name": "get_node",
                "description": "Get one node.",
                "parameters": TOOL.parameters,
                "strict": False,
            }
        ]
        assert request["reasoning"] == {"effort": "high"}
        assert request["max_output_tokens"] == 99
        assert request["store"] is False
        assert request["include"] == ["reasoning.encrypted_content"]

    def test_round_state_is_sent_back_verbatim(self):
        state = [{"type": "reasoning", "id": "rs_1"}, {"type": "function_call", "id": "fc_1", "call_id": "c1"}]
        items = ResponsesAdapter.input(
            [
                Message("user", "hi"),
                AssistantRound("", [ToolCall("c1", "get_node", {"id": 7})], state=state),
                ToolResult("c1", "get_node", "{}"),
            ]
        )
        assert items == [
            {"role": "user", "content": "hi"},
            *state,
            {"type": "function_call_output", "call_id": "c1", "output": "{}"},
        ]

    def test_round_without_state_is_rebuilt(self):
        items = ResponsesAdapter.input([AssistantRound("Checking.", [ToolCall("c1", "get_node", {"id": 7})])])
        assert items == [
            {"role": "assistant", "content": "Checking."},
            {"type": "function_call", "call_id": "c1", "name": "get_node", "arguments": json.dumps({"id": 7})},
        ]
