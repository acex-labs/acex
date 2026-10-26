"""Workflows: steps on a graph from start to end, and the runs that walk it.

Each box on the graph is a step: what it does, and for steps on nodes, which nodes. A step names the artifacts
it leaves, each an expression over its own `result`; later steps read them by name. A workflow is saved as it
is drawn, finished or not: what keeps it from running is reported as its problems. A run keeps a copy of the
workflow as it was when it started.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.job import JobState
from acex_devkit.workflows.expressions import Expression

#: A box's key and an artifact's name.
NAME = r"^[A-Za-z_][A-Za-z0-9_]*$"


class ArtifactDef(BaseModel):
    """An artifact a step leaves for later steps: `name` is `expression`, read over `result` (what the step
    just did, per node for a step on nodes) and earlier artifacts. Without an expression it is all of `result`."""

    name: str = Field(pattern=NAME)
    expression: str = ""

    @field_validator("name")
    @classmethod
    def _not_reserved(cls, name: str) -> str:
        if name in Expression.RESERVED:
            raise ValueError(f"{name} is a word of the expression language")
        return name


class StepBase(BaseModel):
    artifacts: list[ArtifactDef] = []


class ExecuteStep(StepBase):
    """Raw commands on each node, in order; `{expressions}` in them are rendered per node.
    Result: `output` (every command's output) and `outputs` (each command and its output)."""

    type: Literal["execute"] = "execute"
    commands: list[str] = []


class ActionStep(StepBase):
    """An abstract action run from each node, e.g. ping. Text params may hold `{expressions}`.
    Result: the action's result, e.g. ping's success, success_rate, sent, received, rtt_avg_ms."""

    type: Literal["action"] = "action"
    action: str = "ping"
    params: dict[str, Any] = {}


class ProbeStep(StepBase):
    """A check run from ACEX itself: on each of the step's nodes against its management IP, or once against
    `address`, which may hold `{expressions}`. Result: as ping's, plus the `address` pinged."""

    type: Literal["probe"] = "probe"
    method: Literal["ping"] = "ping"
    address: str | None = None
    count: int = Field(3, ge=1, le=100)
    #: Seconds to wait for each reply.
    timeout: float = Field(2, gt=0, le=60)


class ComputeStep(StepBase):
    """Only artifacts, computed from earlier ones. It has no result of its own."""

    type: Literal["compute"] = "compute"


class AssertStep(StepBase):
    """Checks on earlier artifacts. A check that reads per-node values must hold on every node. When the checks
    don't pass, as all or any of them, the step fails and so does the run. Result: `passed`, `checks`."""

    type: Literal["assert"] = "assert"
    checks: list[str] = []
    require: Literal["all", "any"] = "all"


class ConditionStep(StepBase):
    """Chooses the way on: the edges from its true or its false side. `check` must give one value for the whole
    run, so per-node values are read through all, any, percent or count. Result: `value`."""

    type: Literal["condition"] = "condition"
    check: str = ""


class WaitStep(StepBase):
    """Waits, without holding a worker. Result: `seconds`."""

    type: Literal["wait"] = "wait"
    seconds: int = Field(60, ge=1, le=7 * 24 * 3600)


StepConfig = Annotated[
    ExecuteStep | ActionStep | ProbeStep | ComputeStep | AssertStep | ConditionStep | WaitStep,
    Field(discriminator="type"),
]

STEP_TYPES = ("execute", "action", "probe", "compute", "assert", "condition", "wait")


class GraphNode(BaseModel):
    """A box on the canvas: the start, the end, or a step. `key` names it within the workflow."""

    key: str = Field(pattern=NAME)
    kind: Literal["start", "end", "step"] = "step"
    #: What the box is called on the canvas.
    name: str = ""
    step: StepConfig | None = None
    #: The nodes a step on nodes runs on.
    targets: list[int] = []
    position: dict[str, float] | None = None

    @property
    def on_nodes(self) -> bool:
        """Whether the step runs as one job per node: execute and action always, a probe when it has nodes."""
        if self.step is None:
            return False
        return self.step.type in ("execute", "action") or (self.step.type == "probe" and bool(self.targets))


class GraphEdge(BaseModel):
    source: str
    target: str
    #: For an edge from a condition: the side it leaves from.
    branch: Literal["true", "false"] | None = None


class WorkflowGraph(BaseModel):
    """Exactly one start and one end. Edges may branch (parallel), leave a condition on one side, and loop
    back; a step with several edges in waits for each of them that can still fire."""

    nodes: list[GraphNode] = Field(
        default_factory=lambda: [GraphNode(key="start", kind="start"), GraphNode(key="end", kind="end")]
    )
    edges: list[GraphEdge] = []

    @model_validator(mode="after")
    def _shape(self) -> "WorkflowGraph":
        keys = [node.key for node in self.nodes]
        if len(keys) != len(set(keys)):
            raise ValueError("node keys must be unique")
        kinds = [node.kind for node in self.nodes]
        if kinds.count("start") != 1 or kinds.count("end") != 1:
            raise ValueError("a workflow has exactly one start and one end")
        start = next(node.key for node in self.nodes if node.kind == "start")
        end = next(node.key for node in self.nodes if node.kind == "end")
        for node in self.nodes:
            if node.kind == "step" and node.step is None:
                raise ValueError(f"{node.key} has no step")
        conditions = {node.key for node in self.nodes if node.step is not None and node.step.type == "condition"}
        for edge in self.edges:
            if edge.source not in keys or edge.target not in keys:
                raise ValueError(f"edge {edge.source} -> {edge.target} joins a node that isn't there")
            if edge.target == start or edge.source == end:
                raise ValueError("nothing leads into start, and nothing leaves end")
            if (edge.branch is not None) != (edge.source in conditions):
                raise ValueError(f"edge {edge.source} -> {edge.target}: only edges from a condition take a side")
        names = [artifact.name for node in self.nodes if node.step for artifact in node.step.artifacts]
        doubles = sorted({name for name in names if names.count(name) > 1})
        if doubles:
            raise ValueError(f"artifact names must be unique: {', '.join(doubles)}")
        return self

    def node(self, key: str) -> GraphNode:
        return next(node for node in self.nodes if node.key == key)

    def outgoing(self, key: str, branch: str | None = None) -> list[str]:
        """Where `key`'s edges lead: all of them, or from a condition only those of side `branch`."""
        return [e.target for e in self.edges if e.source == key and (branch is None or e.branch == branch)]

    def incoming(self, key: str) -> list[str]:
        return [edge.source for edge in self.edges if edge.target == key]

    def producers(self) -> dict[str, str]:
        """The key of the step that leaves each artifact, by artifact name."""
        return {a.name: node.key for node in self.nodes if node.step for a in node.step.artifacts}


class WorkflowBase(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    #: How many times a step may run in one run before the run fails: a guard against loops that never end.
    max_rounds: int = Field(100, ge=1, le=100_000)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    graph: WorkflowGraph | None = None
    max_rounds: int | None = Field(None, ge=1, le=100_000)


class UpstreamArtifact(BaseModel):
    """An artifact a step can read: made by a step before it, possibly in an earlier round of a loop."""

    name: str
    #: The key of the step that leaves it.
    step: str
    #: Whether it has a value per node, rather than one for the whole run.
    per_node: bool
    #: For one that is all of its step's result: the result's fields, e.g. success_rate.
    fields: list[str] = []


class WorkflowCheck(BaseModel):
    """What stands in the way of running a workflow, and what is worth a second look, by box key; the workflow
    as a whole is under "". Problems keep a run from starting; warnings don't."""

    problems: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}
    #: For each step, the artifacts of the steps before it.
    upstream: dict[str, list[UpstreamArtifact]] = {}


class WorkflowResponse(PersistedResponse, WorkflowBase):
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
    check: WorkflowCheck = WorkflowCheck()


class WorkflowRunMode(StrEnum):
    #: Step after step until the end.
    run = "run"
    #: Pause after each step, to look at its artifacts before going on.
    evaluate = "evaluate"
    #: Walk the graph without reaching any device: steps on nodes show what they would send, a condition
    #: takes both ways and a wait doesn't wait.
    dry_run = "dry_run"


class WorkflowRunRequest(BaseModel):
    mode: WorkflowRunMode = WorkflowRunMode.run


class WorkflowRunData(BaseModel):
    """A workflow run's job data: what it runs, frozen at the start, and how far it has come."""

    workflow_id: int
    name: str
    mode: WorkflowRunMode
    #: The workflow as it was when the run started.
    graph: WorkflowGraph
    max_rounds: int = 100
    #: Hostnames of every step's nodes, by node id, as they were at the start.
    hostnames: dict[int, str] = {}
    #: Bookkeeping: for each step waiting to start, the steps whose edges into it have fired.
    fired: dict[str, list[str]] = {}
    #: Steps started and not yet finished.
    active: list[str] = []
    #: In evaluate mode, the steps whose edges fire on continue.
    pending: list[str] = []
    #: How many times each step has run, so a loop's latest round is told apart.
    rounds: dict[str, int] = {}
    #: The side each condition took last.
    branches: dict[str, Literal["true", "false"]] = {}


class WorkflowStepJob(BaseModel):
    """Data of a step's job: one round of a step in a run. A step on nodes runs as one WorkflowNodeJob per node
    under it; other steps run as this job."""

    run_id: int
    key: str
    round: int = 1


class WorkflowNodeJob(WorkflowStepJob):
    node_id: int


class WorkflowWaitJob(WorkflowStepJob):
    """A wait's job: the backend finishes it when its time has come, at once in a dry run."""

    seconds: int
    dry_run: bool = False


class WorkflowNodeResult(BaseModel):
    """What one node's job in a step reports: what it did, and the step's artifacts for this node."""

    result: dict[str, Any] | None = None
    artifacts: dict[str, Any] = {}


class ArtifactValue(BaseModel):
    """An artifact's value: one for the whole run, or one per node by hostname."""

    value: Any = None
    nodes: dict[str, Any] | None = None


class WorkflowStepResult(BaseModel):
    """What a step's job that runs once reports: what it did, and the artifacts it leaves."""

    result: dict[str, Any] | None = None
    artifacts: dict[str, ArtifactValue] = {}


class RunArtifact(ArtifactValue):
    """An artifact in a run: from the latest finished round of the step that leaves it."""

    step: str
    round: int


class WorkflowArtifacts(BaseModel):
    artifacts: dict[str, RunArtifact] = {}  # by name


class WorkflowStepRun(BaseModel):
    """One round of a step in a run: its job."""

    key: str
    round: int
    job_id: int
    state: JobState
    #: For a step on nodes: how many of its node jobs are in each state.
    jobs: dict[JobState, int] | None = None
    #: For a step that runs once: what it reported. A step on nodes has its nodes' answers instead.
    result: WorkflowStepResult | None = None
    error: str | None = None
    created_at: datetime
    #: For a wait: when it ends.
    run_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRun(BaseModel):
    id: int
    workflow_id: int
    #: The workflow's name when the run started.
    name: str
    mode: WorkflowRunMode
    #: Kept by the run itself: running, paused (evaluate mode), or how it ended.
    state: JobState
    error: str | None = None
    created_by: str
    created_at: datetime
    finished_at: datetime | None = None


class WorkflowRunDetail(WorkflowRun):
    """A run with what it runs and how far it has come."""

    graph: WorkflowGraph
    hostnames: dict[int, str] = {}
    #: Steps running now.
    active: list[str] = []
    #: In evaluate mode, the finished steps whose edges fire on continue.
    pending: list[str] = []
    #: The side each condition took last.
    branches: dict[str, Literal["true", "false"]] = {}
    #: Every round of every step so far, oldest first.
    step_runs: list[WorkflowStepRun] = []
