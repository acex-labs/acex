"""Tool loop: rounds, tools, answer text, usage."""

import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import mcp.types as mt
import pytest
from acex.ai_ops.config import AIModelConfig
from acex.ai_ops.events import NavigateEvent, PlanEvent, ToolCallEvent, UsageEvent
from acex.ai_ops.loop import FINAL_ANSWER_NUDGE, NO_ANSWER, TOOL_CALL_AS_TEXT, ToolSyntaxFilter
from acex.ai_ops.tools import ANALYSIS_LOCAL_TOOLS, CHAT_LOCAL_TOOLS, LOCAL_TOOLS, Toolbox
from acex.ai_ops.types import AssistantRound, Message, RoundState, TextDelta, ToolCall, ToolResult, Usage
from ai_ops_fakes import FakeAdapter, manager

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _call(name, arguments, call_id="c1"):
    return ToolCall(call_id, name, arguments, json.dumps(arguments))


async def _ask(m, prompt="q", **kwargs):
    return [piece async for piece in m.ask(prompt, **kwargs)]


def _text(pieces):
    return "".join(p for p in pieces if isinstance(p, str))


class TestRounds:
    async def test_a_text_answer_ends_the_loop(self):
        p1 = FakeAdapter([TextDelta("The "), TextDelta("answer.")])
        assert _text(await _ask(manager(p1=p1))) == "The answer."
        assert len(p1.turns) == 1

    async def test_tool_results_go_back_to_the_model(self):
        state = [{"type": "reasoning"}]
        p1 = FakeAdapter(
            [_call("plan", {"steps": [{"description": "look"}]}), RoundState(state)],
            [TextDelta("Done.")],
        )
        pieces = await _ask(manager(p1=p1))
        assert _text(pieces) == "Done."
        conversation = p1.turns[1].conversation
        assert isinstance(conversation[-2], AssistantRound) and conversation[-2].state == state
        assert isinstance(conversation[-1], ToolResult) and conversation[-1].call_id == "c1"

    async def test_text_from_successive_rounds_is_set_apart(self):
        p1 = FakeAdapter([TextDelta("Looking."), _call("plan", {"steps": []})], [TextDelta("Found it.")])
        assert _text(await _ask(manager(p1=p1))) == "Looking.\n\nFound it."

    async def test_closing_round_when_rounds_run_out(self):
        rounds = [[_call("plan", {"steps": []}, f"c{i}")] for i in range(5)]
        p1 = FakeAdapter(*rounds, [TextDelta("Summary.")])
        assert _text(await _ask(manager(p1=p1))) == "Summary."
        closing = p1.turns[-1]
        assert closing.tool_choice == "none"
        assert closing.conversation[-1] == Message("user", FINAL_ANSWER_NUDGE)

    async def test_empty_answers_end_with_an_honest_sentence(self):
        p1 = FakeAdapter([], [], [])
        assert _text(await _ask(manager(p1=p1))) == NO_ANSWER
        assert len(p1.turns) == 3

    async def test_history_and_context(self):
        p1 = FakeAdapter([TextDelta("ok")])
        m = manager(p1=p1)
        await _ask(
            m,
            "now",
            conversation_history=[{"role": "user", "content": "before"}, {"role": "tool", "content": "skip"}],
            context="page",
            extra_system_prompts=["extra"],
        )
        conversation = p1.turns[0].conversation
        assert conversation[1:] == [
            Message("system", "extra"),
            Message("system", "Page context:\npage"),
            Message("user", "before"),
            Message("user", "now"),
        ]

    async def test_max_tokens_per_task(self):
        p1 = FakeAdapter([TextDelta("a")], [TextDelta("b")])
        m = manager(p1=p1)
        await _ask(m)
        [piece async for piece in m.analyze_config_diff("explain", "-x\n+y")]
        assert p1.turns[0].max_tokens is None
        assert p1.turns[1].max_tokens == 4096


class TestToolSyntaxAsText:
    async def test_model_is_asked_to_make_the_call_properly(self):
        p1 = FakeAdapter([TextDelta("<tool_call>get_node</tool_call>")], [TextDelta("Node 2.")])
        assert _text(await _ask(manager(p1=p1))) == "Node 2."
        assert p1.turns[1].conversation[-1] == Message("user", TOOL_CALL_AS_TEXT)

    async def test_syntax_never_reaches_the_user(self):
        """Also when the marker is split over two streamed pieces."""
        p1 = FakeAdapter(
            [TextDelta("Answer. "), TextDelta("<tool"), TextDelta("_call>x</tool_call> tail")],
            [TextDelta("Final.")],
        )
        assert _text(await _ask(manager(p1=p1))) == "Answer. \n\nFinal."

    def test_partial_marker_is_held_back(self):
        assert ToolSyntaxFilter.hold("hello <tool") == ("hello ", "<tool")
        assert ToolSyntaxFilter.hold("hello world") == ("hello world", "")


class TestUsage:
    async def test_summed_over_rounds_with_cost(self):
        p1 = FakeAdapter(
            [_call("plan", {"steps": []}), Usage(prompt_tokens=100, completion_tokens=10)],
            [TextDelta("ok"), Usage(prompt_tokens=200, completion_tokens=20, reasoning_tokens=5)],
        )
        m = manager(p1=p1)
        m.settings.providers["p1"].models = {
            "m1": AIModelConfig(input_cost_per_mtok=1.0, output_cost_per_mtok=1.0, currency="EUR")
        }
        (usage,) = [p.data for p in await _ask(m) if isinstance(p, UsageEvent)]
        assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (300, 30, 330)
        assert usage["reasoning_tokens"] == 5
        assert (usage["provider"], usage["model"], usage["currency"]) == ("p1", "m1", "EUR")
        assert usage["cost"] == 0.00033
        assert usage["tokens_per_second"] is not None

    async def test_none_when_the_provider_reports_none(self):
        assert not [p for p in await _ask(manager(p1=FakeAdapter([TextDelta("ok")]))) if isinstance(p, UsageEvent)]


class TestLocalTools:
    def test_offered_per_task(self):
        assert "plan" in CHAT_LOCAL_TOOLS and "plan" in ANALYSIS_LOCAL_TOOLS
        assert "navigate_to" in CHAT_LOCAL_TOOLS and "navigate_to" not in ANALYSIS_LOCAL_TOOLS
        assert set(CHAT_LOCAL_TOOLS) | set(ANALYSIS_LOCAL_TOOLS) <= set(LOCAL_TOOLS)

    async def test_offered_without_mcp(self):
        p1 = FakeAdapter([TextDelta("ok")])
        await _ask(manager(p1=p1))
        assert [t.name for t in p1.turns[0].tools] == ["plan", "navigate_to"]

    async def test_plan_becomes_an_event(self):
        steps = [{"description": "Find neighbours on Gi1/0/2", "tool": "get_neighbors"}, "junk"]
        p1 = FakeAdapter([_call("plan", {"goal": "Assess", "steps": steps})], [TextDelta("done")])
        (plan,) = [p for p in await _ask(manager(p1=p1)) if isinstance(p, PlanEvent)]
        assert (plan.goal, plan.steps) == ("Assess", steps[:1])

    async def test_navigate_becomes_an_event(self):
        p1 = FakeAdapter([_call("navigate_to", {"page": "dashboard", "label": "Go"})], [TextDelta("ok")])
        (nav,) = [p for p in await _ask(manager(p1=p1)) if isinstance(p, NavigateEvent)]
        assert nav.data == {"page": "dashboard", "label": "Go"}

    async def test_invalid_arguments_are_reported_to_the_model(self):
        p1 = FakeAdapter([ToolCall("c1", "plan", None, "{bad")], [TextDelta("ok")])
        await _ask(manager(p1=p1))
        assert "not a valid JSON object" in p1.turns[1].conversation[-1].output


class TestMcpTools:
    def test_input_schema_reaches_the_model(self):
        """MCP calls the schema `inputSchema`; reading the wrong field silently
        advertises every tool as taking no arguments."""
        schema = {"type": "object", "properties": {"node_id": {"type": "integer"}}, "required": ["node_id"]}
        (spec,) = Toolbox(
            (), mcp_tools=[mt.Tool(name="get_node", description="Get one node.", inputSchema=schema)]
        ).specs
        assert (spec.name, spec.description, spec.parameters) == ("get_node", "Get one node.", schema)

    async def _run(self, toolbox, call):
        return [item async for item in toolbox.run(call)]

    async def test_call_is_forwarded(self):
        mcp = NS(call_tool=AsyncMock(return_value=NS(content=[NS(text='{"id": 7}')])))
        items = await self._run(Toolbox((), mcp, []), _call("get_node", {"id": 7}))
        mcp.call_tool.assert_awaited_once_with("get_node", arguments={"id": 7})
        assert items[:2] == [ToolCallEvent("get_node", "running"), ToolCallEvent("get_node", "ok")]
        assert items[2] == ToolResult("c1", "get_node", '{"id": 7}')

    async def test_failure_is_reported(self):
        mcp = NS(call_tool=AsyncMock(side_effect=RuntimeError("boom")))
        items = await self._run(Toolbox((), mcp, []), _call("get_node", {}))
        assert items[1] == ToolCallEvent("get_node", "error", "boom")
        assert json.loads(items[2].output) == {"error": "boom"}

    async def test_without_mcp(self):
        items = await self._run(Toolbox(()), _call("get_node", {}))
        assert items[0] == ToolCallEvent("get_node", "error", "MCP tool server unavailable")
