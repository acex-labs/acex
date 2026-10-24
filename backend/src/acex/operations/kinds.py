"""The operations a run can be made of: raw commands, and the abstract actions drivers implement."""

from typing import Any

from acex_devkit.models.actions import ActionParams, PingParams, PingResult
from acex_devkit.models.operations import (
    ActionData,
    ActionRequest,
    ExecuteData,
    ExecuteRequest,
    ExecuteResult,
    NodeSelection,
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


EXECUTE = Execute()

#: Every abstract action a run can be made of. One route and one job type each.
ACTIONS = [Action(PingParams, PingResult)]

OPERATIONS: dict[str, Operation] = {operation.job_type: operation for operation in [EXECUTE, *ACTIONS]}
