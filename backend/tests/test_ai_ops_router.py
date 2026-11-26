"""Model router: failover, layered settings, capabilities, cut-downs."""

import pytest
from acex.ai_ops.config import AIChainLevel, AIModelConfig
from acex.ai_ops.errors import AllLevelsExhaustedError, ProviderError
from acex.ai_ops.types import TextDelta, ToolSpec, Turn
from ai_ops_fakes import FakeAdapter, manager

pytestmark = pytest.mark.anyio

TOOL = ToolSpec("get_node", "", {"type": "object"})


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _turn(**fields):
    return Turn(model="", conversation=[], **fields)


async def _run(session, turn=None):
    return [event async for event in session.stream(turn or _turn())]


class TestFailover:
    async def test_first_level_answers(self):
        p1, p2 = FakeAdapter([TextDelta("hi")]), FakeAdapter()
        m = manager(p1=p1, p2=p2)
        session = m.router.session("chat")
        assert await _run(session) == [TextDelta("hi")]
        assert session.target.level.label == "p1/m1"
        assert not p2.turns

    @pytest.mark.parametrize("kind", ["transient", "rate_limit"])
    async def test_transient_failures_fail_over(self, kind):
        m = manager(p1=FakeAdapter(ProviderError("x", kind)), p2=FakeAdapter([TextDelta("hi")]))
        session = m.router.session("chat")
        assert await _run(session) == [TextDelta("hi")]
        assert session.target.level.label == "p2/m2"

    @pytest.mark.parametrize("kind", ["auth", "invalid_request"])
    async def test_configuration_problems_fail_at_once(self, kind):
        p2 = FakeAdapter()
        m = manager(p1=FakeAdapter(ProviderError("x", kind)), p2=p2)
        with pytest.raises(ProviderError):
            await _run(m.router.session("chat"))
        assert not p2.turns

    async def test_all_levels_failing(self):
        m = manager(p1=FakeAdapter(ProviderError("a", "transient")), p2=FakeAdapter(ProviderError("b", "transient")))
        with pytest.raises(AllLevelsExhaustedError, match="p1/m1: a; p2/m2: b"):
            await _run(m.router.session("chat"))

    async def test_no_failover_after_output(self):
        p2 = FakeAdapter()
        m = manager(p1=FakeAdapter([TextDelta("hi"), ProviderError("cut", "transient")]), p2=p2)
        with pytest.raises(ProviderError, match="cut"):
            await _run(m.router.session("chat"))
        assert not p2.turns

    async def test_later_rounds_stay_on_the_chosen_level(self):
        p1 = FakeAdapter(ProviderError("x", "transient"))
        p2 = FakeAdapter([TextDelta("one")], [TextDelta("two")])
        m = manager(p1=p1, p2=p2)
        session = m.router.session("chat")
        await _run(session)
        assert await _run(session) == [TextDelta("two")]
        assert len(p1.turns) == 1

    async def test_override_is_pinned(self):
        p2 = FakeAdapter()
        m = manager(p1=FakeAdapter(ProviderError("x", "transient")), p2=p2)
        with pytest.raises(ProviderError):
            await _run(m.router.session("chat", "p1/other"))
        assert not p2.turns

    async def test_unqualified_override_uses_the_first_provider(self):
        p1 = FakeAdapter([TextDelta("hi")])
        m = manager(p1=p1)
        await _run(m.router.session("chat", "custom"))
        assert p1.turns[0].model == "custom"

    def test_override_with_unknown_provider(self):
        with pytest.raises(ValueError, match="unknown provider"):
            manager().router.session("chat", "ghost/m")


class TestSettings:
    async def test_layers_model_then_level_then_request(self):
        p1 = FakeAdapter([], [], [])
        m = manager(p1=p1, chain=("p1/m1",))
        m.settings.providers["p1"].models = {
            "m1": AIModelConfig(reasoning_effort="low", params={"a": "model", "b": "model", "c": "model"})
        }
        level = m.settings.chains["default"][0]
        level.reasoning_effort, level.params = "medium", {"b": "level", "c": "level"}

        await _run(m.router.session("chat"), _turn(params={"c": "request"}))
        turn = p1.turns[0]
        assert turn.model == "m1"
        assert turn.reasoning_effort == "medium"
        assert turn.params == {"a": "model", "b": "level", "c": "request"}

        await _run(m.router.session("chat"), _turn(reasoning_effort="high"))
        assert p1.turns[1].reasoning_effort == "high"

        level.reasoning_effort = None
        await _run(m.router.session("chat"))
        assert p1.turns[2].reasoning_effort == "low"

    async def test_tools_left_out_for_a_model_without_them(self):
        p1 = FakeAdapter([])
        m = manager(p1=p1, chain=("p1/m1",))
        m.settings.providers["p1"].models = {"m1": AIModelConfig(supports_tools=False)}
        await _run(m.router.session("chat"), _turn(tools=[TOOL]))
        assert p1.turns[0].tools == []

    def test_chain_level_from_json(self):
        level = AIChainLevel.model_validate({"provider": "p", "model": "m", "reasoning_effort": "high"})
        assert level.label == "p/m" and level.reasoning_effort == "high"


class TestCutDowns:
    """A model that refuses a feature is asked again without it."""

    @staticmethod
    def _refused(param="reasoning_effort"):
        return ProviderError("refused", "unsupported", 400, param)

    async def test_reasoning_turned_off_keeps_the_tools(self):
        p1 = FakeAdapter(self._refused(), [TextDelta("ok")], [TextDelta("again")])
        m = manager(p1=p1, chain=("p1/m1",))
        assert await _run(m.router.session("chat"), _turn(tools=[TOOL])) == [TextDelta("ok")]
        assert (p1.turns[1].reasoning_effort, p1.turns[1].tools) == ("none", [TOOL])

        await _run(m.router.session("chat"), _turn(tools=[TOOL]))
        assert len(p1.turns) == 3, "remembered: no second refusal"
        assert p1.turns[2].reasoning_effort == "none"

    async def test_tools_dropped_when_reasoning_cannot_be_turned_off(self):
        """gpt-6.1-sol on /chat/completions: reasoning is always on and tools need it off."""
        p1 = FakeAdapter(self._refused(), self._refused(), [TextDelta("ok")])
        m = manager(p1=p1, chain=("p1/m1",))
        m.settings.providers["p1"].models = {"m1": AIModelConfig(reasoning_effort="medium")}
        assert await _run(m.router.session("chat"), _turn(tools=[TOOL])) == [TextDelta("ok")]
        assert (p1.turns[2].reasoning_effort, p1.turns[2].tools) == ("medium", [])

    async def test_refused_tools_are_dropped_directly(self):
        p1 = FakeAdapter(self._refused("tools"), [TextDelta("ok")])
        m = manager(p1=p1, chain=("p1/m1",))
        await _run(m.router.session("chat"), _turn(tools=[TOOL]))
        assert (p1.turns[1].reasoning_effort, p1.turns[1].tools) == (None, [])

    async def test_nothing_left_to_drop(self):
        p1 = FakeAdapter(self._refused("tools"))
        m = manager(p1=p1, chain=("p1/m1",))
        with pytest.raises(ProviderError):
            await _run(m.router.session("chat"))

    async def test_a_refusal_does_not_fail_over(self):
        p2 = FakeAdapter()
        m = manager(p1=FakeAdapter(self._refused("tools")), p2=p2)
        with pytest.raises(ProviderError):
            await _run(m.router.session("chat"))
        assert not p2.turns
