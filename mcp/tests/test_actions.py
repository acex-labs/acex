"""Action tools: made from devkit's ACTIONS, ordered as a run, waited for up to the action's max_wait."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from acex_devkit.models.actions import ACTIONS, ActionSpec
from acex_devkit.models.job import JobState
from acex_devkit.models.operations import NodeResponse, Run, RunReport
from acex_mcp.app import create_app
from acex_mcp.tools import actions
from acex_mcp.tools.actions import ActionTool
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 26, 8, 0, tzinfo=UTC)
RESULT = {"sent": 5, "received": 5, "rtt_min_ms": 1.0, "rtt_avg_ms": 1.2, "rtt_max_ms": 1.5, "success": True}


@pytest.fixture
def anyio_backend():
    return "asyncio"


RUN = {
    "id": 7,
    "type": "acex.operations.actions.ping",
    "state": JobState.queued,
    "jobs": {JobState.queued: 1},
    "created_by": "johan",
    "created_at": NOW,
}


def _report(finished: bool) -> RunReport:
    state = JobState.succeeded if finished else JobState.running
    response = NodeResponse(
        node_id=24,
        hostname="sto-office1-core-1",
        job_id=8,
        state=state,
        result=RESULT if finished else None,
    )
    return RunReport(**{**RUN, "state": state}, finished_at=NOW if finished else None, responses=[response])


@pytest.fixture
def backend(monkeypatch):
    """The backend client the tools call, with no waiting between looks at a run."""
    fake = MagicMock()
    fake.operations.actions.run.return_value = Run(**RUN)
    monkeypatch.setattr(actions, "client", lambda: fake)
    monkeypatch.setattr(actions, "POLL_INTERVAL", 0)
    return fake


class TestTools:
    async def test_one_tool_per_action(self):
        tools = await create_app().get_tools()
        assert set(ACTIONS) <= set(tools)
        assert all(isinstance(tools[name], ActionTool) for name in ACTIONS)

    def test_arguments_are_node_id_and_the_params(self):
        tool = ActionTool.for_action(ACTIONS["ping"])
        properties = tool.parameters["properties"]
        assert list(properties)[0] == "node_id"
        assert set(ACTIONS["ping"].params.model_fields) <= set(properties)
        assert tool.parameters["required"] == ["node_id", "target"]
        assert properties["target"]["description"]

    def test_described_from_the_params_and_the_wait(self):
        description = ActionTool.for_action(ACTIONS["ping"]).description
        assert ACTIONS["ping"].description in description
        assert "60 seconds" in description and "get_action_run" in description

    def test_live_but_changing_nothing(self):
        annotations = ActionTool.for_action(ACTIONS["ping"]).annotations
        assert annotations.readOnlyHint is True and annotations.openWorldHint is True


class TestRun:
    async def test_orders_one_node_and_waits_for_the_answer(self, backend):
        backend.operations.runs.get.side_effect = [_report(False), _report(True)]
        result = await ActionTool.for_action(ACTIONS["ping"]).run({"node_id": 24, "target": "10.10.0.2", "count": 5})

        args, kwargs = backend.operations.actions.run.call_args
        assert args == ("ping", [24])
        assert kwargs == {"target": "10.10.0.2", "count": 5, "timeout": 2}
        answer = result.structured_content
        assert answer["finished"] is True and "note" not in answer
        assert answer["responses"][0]["result"]["received"] == 5
        assert answer["responses"][0]["hostname"] == "sto-office1-core-1"

    async def test_stops_waiting_at_max_wait(self, backend, monkeypatch):
        ping = ACTIONS["ping"]
        monkeypatch.setitem(ACTIONS, "ping", ActionSpec(ping.params, ping.result, max_wait=0))
        backend.operations.runs.get.return_value = _report(False)
        result = await ActionTool.for_action(ACTIONS["ping"]).run({"node_id": 24, "target": "10.10.0.2"})
        answer = result.structured_content
        assert answer["finished"] is False
        assert answer["run_id"] == 7 and "get_action_run" in answer["note"]

    async def test_invalid_params_are_refused_before_ordering(self, backend):
        with pytest.raises(ToolError, match="Invalid ping params"):
            await ActionTool.for_action(ACTIONS["ping"]).run({"node_id": 24, "target": "x", "count": 0})
        backend.operations.actions.run.assert_not_called()

    async def test_node_id_is_required(self, backend):
        with pytest.raises(ToolError, match="find_nodes"):
            await ActionTool.for_action(ACTIONS["ping"]).run({"target": "x"})


class TestGetActionRun:
    async def test_reads_a_run(self, backend):
        backend.operations.runs.get.return_value = _report(True)
        tool = (await create_app().get_tools())["get_action_run"]
        result = await tool.run({"run_id": 7})
        backend.operations.runs.get.assert_called_once_with(run_id=7)
        assert result.structured_content["responses"][0]["state"] == "succeeded"
