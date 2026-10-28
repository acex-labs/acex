"""Operations on nodes: raw commands and abstract actions, ordered as runs of one job per node."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field, field_validator

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


class PatchScope(BaseModel):
    """How far a patch reaches into the configuration tree."""

    #: A dotted path such as `system.ntp.servers`; empty for the whole tree. The patch reaches what is at the
    #: path and below it, nothing else.
    path: str = ""
    #: Also remove what the device holds there that the desired configuration doesn't declare.
    prune: bool = False

    @field_validator("path")
    @classmethod
    def _trimmed(cls, path: str) -> str:
        return path.strip().strip(".")


class PatchRenderRequest(PatchScope, NodeSelection):
    """Render, on each node, the patch that brings its configuration at `path` to the desired state. Each node
    is read live; nothing is sent."""


class PatchRenderData(PatchScope):
    """Data of an acex.operations.patch.render job: the patch to render on one node."""

    node_id: int


class PatchChange(BaseModel):
    """A component a patch adds, changes or removes."""

    op: str
    path: str
    #: For a change, the attributes that change.
    attributes: list[str] = []


class PatchRenderResult(BaseModel):
    """Result of an acex.operations.patch.render job: what the node would be sent."""

    #: Masked by the node's NED. Empty when the node already matches.
    patch: str = ""
    #: Of the patch as rendered, before masking: an apply sends only a patch that hashes the same. None when
    #: the node already matches.
    patch_hash: str | None = None
    #: What the patch changes.
    changes: list[PatchChange] = []
    #: What differs that the node's NED can't write, so the patch leaves it out.
    unrendered: list[PatchChange] = []

    @computed_field
    @property
    def in_sync(self) -> bool:
        return not self.changes and not self.unrendered


class PatchApplyRequest(NodeSelection):
    """Apply a rendered plan on some of its nodes. Each node is read live again and sent its patch only if
    it still renders the one the plan holds."""

    plan_id: int


class PatchApplyData(PatchScope):
    """Data of an acex.operations.patch.apply job: the plan's scope and patch for one node."""

    node_id: int
    plan_id: int
    patch_hash: str


class PatchOutcome(StrEnum):
    #: Sent, and nothing differs at the path any more.
    applied = "applied"
    #: Sent, but the node still differs at the path.
    residual = "residual"
    #: Not sent: the node renders another patch than the plan's, so it changed since.
    changed = "changed"


class PatchApplyResult(BaseModel):
    """Result of an acex.operations.patch.apply job."""

    outcome: PatchOutcome
    #: What was sent, masked by the node's NED.
    patch: str = ""
    #: What the device answered, masked.
    output: str = ""
    #: What differs at the path now that the NED can write: after the patch, or instead of the plan when it no
    #: longer holds.
    changes: list[PatchChange] = []
    #: What differs that the node's NED can't write, left out of the patch and of the verification.
    unrendered: list[PatchChange] = []


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
    #: When the last of its jobs finished, once every one has; None while any is queued or running.
    finished_at: datetime | None = None


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
