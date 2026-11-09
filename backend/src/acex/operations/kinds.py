"""The operations a run can be made of: raw commands, and the abstract actions drivers implement."""

from typing import Any

from acex_devkit.models.actions import ActionParams, PingParams, PingResult
from acex_devkit.models.job import JobResponse, JobState
from acex_devkit.models.operations import (
    ActionData,
    ActionRequest,
    ExecuteData,
    ExecuteRequest,
    ExecuteResult,
    NodeSelection,
    PatchApplyData,
    PatchApplyRequest,
    PatchApplyResult,
    PatchRenderData,
    PatchRenderRequest,
    PatchRenderResult,
    PatchScope,
)
from pydantic import BaseModel


class Operation:
    """One kind of operation: the job type its runs are made of, the request it takes, the NED capability
    a node needs for it, and how a node's result reads as report rows."""

    job_type: str
    request: type[NodeSelection]
    data: type[BaseModel]
    result: type[BaseModel]
    #: Where in a NED's capabilities, and under what name: ("operations", "execute"), ("actions", "ping").
    capability: tuple[str, str]
    #: The result's columns in a report.
    columns: tuple[str, ...]

    def items(self, request: NodeSelection) -> list[BaseModel]:
        """One job's data per node."""
        raise NotImplementedError

    def cells(self, result: dict | None) -> list[dict[str, Any]]:
        """A node's result as report rows, one per row it fills; a node without a result fills one empty row."""
        raise NotImplementedError

    def supported_by(self, capabilities: BaseModel | None) -> bool:
        kind, name = self.capability
        return capabilities is not None and name in getattr(capabilities, kind)


class Execute(Operation):
    job_type = "acex.operations.execute"
    request = ExecuteRequest
    data = ExecuteData
    result = ExecuteResult
    capability = ("operations", "execute")
    columns = ("command", "output")

    def items(self, request: ExecuteRequest) -> list[BaseModel]:
        return [ExecuteData(node_id=node_id, commands=request.commands) for node_id in request.node_ids]

    def cells(self, result: dict | None) -> list[dict[str, Any]]:
        return [{"command": o["command"], "output": o["output"]} for o in result["outputs"]] if result else [{}]


class Action(Operation):
    """An abstract action, run through the NED's `Actions`: the same params and result for every vendor."""

    def __init__(self, params: type[ActionParams], result: type[BaseModel]):
        self.name = params.action
        self.job_type = f"acex.operations.actions.{self.name}"
        self.request = ActionRequest[params]
        self.data = ActionData[params]
        self.result = result
        self.capability = ("actions", self.name)
        self.columns = (*result.model_fields, *result.model_computed_fields)

    def items(self, request: ActionRequest) -> list[BaseModel]:
        return [self.data(node_id=node_id, params=request.params) for node_id in request.node_ids]

    def cells(self, result: dict | None) -> list[dict[str, Any]]:
        return [{column: result.get(column) for column in self.columns}] if result else [{}]


class Patching(Operation):
    """Reads the node's configuration and writes it, so its NED must do both."""

    capability = ("operations", "apply")

    def supported_by(self, capabilities: BaseModel | None) -> bool:
        return capabilities is not None and {"get_config", "apply"} <= set(capabilities.operations)


class PatchRender(Patching):
    """Renders on each node the patch its configuration needs at a path, from a live read. Sends nothing."""

    job_type = "acex.operations.patch.render"
    request = PatchRenderRequest
    data = PatchRenderData
    result = PatchRenderResult
    columns = ("changes", "patch")

    def items(self, request: PatchRenderRequest) -> list[BaseModel]:
        scope = PatchScope.model_validate(request, from_attributes=True).model_dump()
        return [PatchRenderData(node_id=node_id, **scope) for node_id in request.node_ids]

    def cells(self, result: dict | None) -> list[dict[str, Any]]:
        return [{"changes": len(result["changes"]), "patch": result["patch"]}] if result else [{}]


class PatchApply(Patching):
    """Sends a plan's patches: each node is read again and patched only if it still renders the plan's patch."""

    job_type = "acex.operations.patch.apply"
    request = PatchApplyRequest
    data = PatchApplyData
    result = PatchApplyResult
    columns = ("outcome", "patch", "output")

    def planned(self, rendered: list[JobResponse]) -> dict[int, str]:
        """The hash of each patch a plan rendered, by node; nodes in sync or failed have none."""
        return {
            job.subject_id: job.result["patch_hash"]
            for job in rendered
            if job.state == JobState.succeeded and job.result and job.result.get("patch_hash")
        }

    def items_from(self, request: PatchApplyRequest, plan: JobResponse, hashes: dict[int, str]) -> list[BaseModel]:
        scope = PatchScope.model_validate(plan.data or {})
        return [
            PatchApplyData(node_id=node_id, plan_id=plan.id, patch_hash=hashes[node_id], **scope.model_dump())
            for node_id in request.node_ids
        ]

    def cells(self, result: dict | None) -> list[dict[str, Any]]:
        return [{column: result.get(column) for column in self.columns}] if result else [{}]


EXECUTE = Execute()

#: Every abstract action a run can be made of. One route and one job type each.
ACTIONS = [Action(PingParams, PingResult)]

PATCH_RENDER = PatchRender()
PATCH_APPLY = PatchApply()

OPERATIONS: dict[str, Operation] = {
    operation.job_type: operation for operation in [EXECUTE, *ACTIONS, PATCH_RENDER, PATCH_APPLY]
}
