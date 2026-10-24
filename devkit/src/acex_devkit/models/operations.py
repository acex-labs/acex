"""Operations on nodes: raw commands and abstract actions, ordered as runs of one job per node."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from acex_devkit.models.actions import ActionParams
from acex_devkit.models.job import JobState


class NodeSelection(BaseModel):
    """The nodes an operation runs on, each once."""

    node_ids: list[int] = Field(min_length=1)

    @field_validator("node_ids")
    @classmethod
    def _once_each(cls, node_ids: list[int]) -> list[int]:
        return list(dict.fromkeys(node_ids))


class ExecuteRequest(NodeSelection):
    """Run the same raw, vendor-specific commands on each node, in order."""

    commands: list[str] = Field(min_length=1)

    @field_validator("commands")
    @classmethod
    def _not_blank(cls, commands: list[str]) -> list[str]:
        commands = [command.strip() for command in commands]
        if not all(commands):
            raise ValueError("commands must not be blank")
        return commands


class ExecuteData(BaseModel):
    """Data of an acex.operations.execute job: commands to run on one node."""

    node_id: int
    commands: list[str] = Field(min_length=1)


class CommandOutput(BaseModel):
    command: str
    #: Masked by the node's NED: secrets the device prints are never stored.
    output: str


class ExecuteResult(BaseModel):
    """Result of an acex.operations.execute job: what the node answered, command by command."""

    outputs: list[CommandOutput]


class ActionRequest[P: ActionParams](NodeSelection):
    """Run one abstract action, with the same params, on each node."""

    params: P


class ActionData[P: ActionParams](BaseModel):
    """Data of an acex.operations.actions.<action> job: the action's params for one node."""

    node_id: int
    params: P


class Run(BaseModel):
    """An operation ordered on a number of nodes: the batch of their jobs."""

    id: int
    #: The job type of the run's jobs, e.g. "acex.operations.execute".
    type: str
    #: Derived from the jobs: running until every one has finished.
    state: JobState
    #: How many of the run's jobs are in each state.
    jobs: dict[JobState, int]
    #: The commands or action params as ordered.
    request: dict | None = None
    created_by: str
    created_at: datetime


class NodeResponse(BaseModel):
    """What one node answered in a run: its job's result, or why it failed."""

    node_id: int
    #: None when the node has been deleted since.
    hostname: str | None = None
    job_id: int
    state: JobState
    #: The operation's result model, as data: ExecuteResult or the action's result.
    result: dict | None = None
    error: str | None = None
    finished_at: datetime | None = None


class RunReport(Run):
    """A run with every node's response, sorted by hostname."""

    responses: list[NodeResponse] = []
