"""Actions run live on a node: one tool per action in devkit's ACTIONS, plus get_action_run().

An action is ordered as a run, like from Operations › Standard Actions, and a worker carries it out
through the node's driver. The tool waits for the answer up to the action's own max_wait. A run that
takes longer goes on by itself, and the model reads it later with get_action_run() instead of ordering
it again.
"""

import asyncio
import time
from typing import Any

from acex_devkit.models.actions import ACTIONS, ActionSpec
from acex_devkit.models.operations import RunReport
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_context
from fastmcp.tools.tool import Tool, ToolResult
from pydantic import ValidationError

from ..backend import call, client

#: Live on a device, but changing nothing there or in ACE-X.
ACTION_ANNOTATIONS: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": True}

#: Reading a run ACE-X has recorded.
READ_ONLY: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}

#: Seconds between looks at a run while waiting for it.
POLL_INTERVAL = 1.0


class ActionTool(Tool):
    """One action, run on one node. Its arguments are node_id plus the action's params, flattened."""

    action: str

    @classmethod
    def for_action(cls, spec: ActionSpec) -> "ActionTool":
        schema = spec.params.model_json_schema()
        parameters = {
            "type": "object",
            "properties": {
                "node_id": {"type": "integer", "description": "The node to run it on, from find_nodes()."},
                **schema.get("properties", {}),
            },
            "required": ["node_id", *schema.get("required", [])],
        }
        if "$defs" in schema:
            parameters["$defs"] = schema["$defs"]
        return cls(
            name=spec.name,
            action=spec.name,
            description=cls.describe(spec),
            parameters=parameters,
            annotations=ACTION_ANNOTATIONS,
        )

    @staticmethod
    def describe(spec: ActionSpec) -> str:
        return (
            f"{spec.description}\n\n"
            "Runs live on the node now, through its driver — unlike an observed configuration, which is a stored "
            "snapshot. It changes nothing on the device. The params and the result are the same for every vendor; "
            f"a node whose driver does not support {spec.name} is refused.\n\n"
            f"Waits up to {spec.max_wait} seconds for the answer. If the run is still going then, the response says "
            "so and gives its run_id: call get_action_run(run_id) later rather than ordering it again. Every run "
            "is recorded in ACE-X under Operations › Standard Actions, as ordered by the user."
        )

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        spec = ACTIONS[self.action]
        arguments = dict(arguments)
        node_id = arguments.pop("node_id", None)
        if node_id is None:
            raise ToolError("node_id is required — use find_nodes() to look the node up.")
        try:
            params = spec.params.model_validate(arguments)
        except ValidationError as exc:
            raise ToolError(f"Invalid {spec.name} params: {exc}") from exc

        run = await call(
            client().operations.actions.run,
            spec.name,
            [node_id],
            doing=f"ordering {spec.name} on node {node_id}",
            **params.model_dump(exclude_none=True),
        )
        report = await self.wait(run.id, spec.max_wait)
        return ToolResult(structured_content=self.answer(report))

    @staticmethod
    async def wait(run_id: int, max_wait: int) -> RunReport:
        """The run once it has finished, or as it stands after max_wait seconds. Reports progress to
        clients that asked for it, which also keeps some of them from timing the call out."""
        started = time.monotonic()
        while True:
            report = await call(client().operations.runs.get, run_id=run_id, doing=f"checking run {run_id}")
            elapsed = time.monotonic() - started
            if report.finished_at is not None or elapsed >= max_wait:
                return report
            try:
                await get_context().report_progress(elapsed, max_wait, f"run {run_id} is {report.state}")
            except RuntimeError:
                pass  # Called outside a request, e.g. in tests: nobody to report to.
            await asyncio.sleep(POLL_INTERVAL)

    @staticmethod
    def answer(report: RunReport) -> dict:
        """A run as a model reads it: each node's result or error, and whether it has finished."""
        answer = {
            "run_id": report.id,
            "action": report.type.rsplit(".", 1)[-1],
            "finished": report.finished_at is not None,
            "ordered_by": report.created_by,
            "ordered_at": report.created_at,
            "finished_at": report.finished_at,
            "responses": [
                {
                    "node_id": response.node_id,
                    "hostname": response.hostname,
                    "state": response.state,
                    "result": response.result,
                    "error": response.error,
                }
                for response in report.responses
            ],
        }
        if not answer["finished"]:
            answer["note"] = "Still running. Call get_action_run(run_id) later for the answer; do not order it again."
        return answer


def register(mcp: FastMCP) -> None:
    for spec in ACTIONS.values():
        mcp.add_tool(ActionTool.for_action(spec))

    @mcp.tool(annotations=READ_ONLY)
    async def get_action_run(run_id: int) -> dict:
        """Get the answer of an action run, such as a ping, ordered earlier.

        Use it when an action tool stopped waiting before its run finished, or for a run someone ordered
        under Operations › Standard Actions. Each node's response has its result, or its error when the
        action failed on that node.

        Args:
            run_id: From an action tool's response.

        If `finished` is still false, the run is still going: say so, and check again later.
        """
        report = await call(client().operations.runs.get, run_id=run_id, doing=f"reading run {run_id}")
        return ActionTool.answer(report)
