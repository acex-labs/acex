"""Workflow runs: the backend walks the graph as the steps' jobs finish. Branches run in parallel, a join waits
for its branches, a condition takes one side, a wait is a scheduled job the backend finishes, a loop goes
round until stopped or out of rounds, a failed step stops the run, evaluate mode pauses after each step, and a
dry run shows each step once."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from acex.jobs import JobManager
from acex.models.job import Job, JobState
from acex.workflows.library import WorkflowLibrary
from acex.workflows.runs import RunConflict, WorkflowRunError, WorkflowRuns
from acex_devkit.models.job import JobUpdate
from acex_devkit.models.workflows import WorkflowCreate, WorkflowRunMode
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

HOSTS = {1: "acc-1", 2: "acc-2", 3: "core-1"}

STEPS = {
    "ping": {
        "type": "action",
        "params": {"target": "10.0.0.1"},
        "artifacts": [{"name": "{key}_up", "expression": "result.success"}],
    },
    "show": {
        "type": "execute",
        "commands": ["show version"],
        "artifacts": [{"name": "{key}_out", "expression": "result.output"}],
    },
    "check": {"type": "assert", "checks": ["true"]},
    "up": {"type": "condition", "check": "true"},
    "pause": {"type": "wait", "seconds": 30},
}


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    configured = True

    def publish(self, job_type: str, job_id: int) -> None:
        pass


class _Operations:
    """Every node exists and supports everything."""

    class nodes:
        @staticmethod
        async def get(node_id):
            return SimpleNamespace(id=int(node_id), logical_node=SimpleNamespace(hostname=HOSTS[int(node_id)]))

    async def supporting(self, operation, node_ids):
        return [await self.nodes.get(n) for n in node_ids]


class _Lab:
    def __init__(self):
        self.db = _Db()
        self.jobs = JobManager(self.db, _Producer())
        self.library = WorkflowLibrary(self.db)
        self.runs = WorkflowRuns(self.jobs, self.library, _Operations())

    def workflow(self, steps: dict[str, str], edges: str, targets: tuple[int, ...] = (1, 2), max_rounds=100) -> int:
        """`steps` maps keys to kinds of STEPS; `edges` reads "start>a a>b:true b>end". Each step's artifacts are
        named after its key."""
        nodes = [{"key": "start", "kind": "start"}, {"key": "end", "kind": "end"}]
        for key, kind in steps.items():
            step = {
                **STEPS[kind],
                "artifacts": [{**a, "name": a["name"].format(key=key)} for a in STEPS[kind].get("artifacts", [])],
            }
            nodes.append({"key": key, "step": step, "targets": list(targets) if kind in ("ping", "show") else []})
        links = []
        for edge in edges.split():
            ends, _, branch = edge.partition(":")
            source, target = ends.split(">")
            links.append({"source": source, "target": target, "branch": branch or None})
        payload = WorkflowCreate.model_validate(
            {"name": "wf", "graph": {"nodes": nodes, "edges": links}, "max_rounds": max_rounds}
        )
        return self.library.create_workflow(payload, created_by="alice").id

    def start(self, workflow_id: int, mode: WorkflowRunMode = WorkflowRunMode.run) -> int:
        return asyncio.run(self.runs.start(workflow_id, mode, "alice")).id

    def waiting(self, state: JobState = JobState.queued) -> list[Job]:
        """Jobs in `state` with nothing under them: for queued, what a worker would pick up."""
        with Session(self.db.engine) as session:
            jobs = session.exec(select(Job).where(Job.state == state)).all()
            parents = {job.parent_id for job in session.exec(select(Job)).all()}
            return [job for job in jobs if job.id not in parents]

    def work(self, key: str, *, fail_on: int | None = None, value: bool = True) -> None:
        """A worker runs every queued job of step `key`; a condition answers `value`."""
        for job in self.waiting():
            if job.data["key"] != key:
                continue
            self.jobs.update(job.id, JobUpdate(state=JobState.running), worker="w")
            node = job.data.get("node_id")
            if node is not None and node == fail_on:
                report = JobUpdate(state=JobState.failed, error="unreachable")
            elif node is not None:
                result = {"success": True, "output": f"Version {node}"}
                artifacts = {f"{key}_up": True, f"{key}_out": f"Version {node}"}
                report = JobUpdate(state=JobState.succeeded, result={"result": result, "artifacts": artifacts})
            elif job.type.endswith(".condition"):
                report = JobUpdate(state=JobState.succeeded, result={"result": {"value": value}})
            else:
                result = {"result": {"passed": True}, "artifacts": {"total": {"value": 2}}}
                report = JobUpdate(state=JobState.succeeded, result=result)
            self.jobs.update(job.id, report, worker="w")

    def keys(self) -> list[str]:
        return sorted({job.data["key"] for job in self.waiting()})

    def state(self, run_id: int) -> JobState:
        return self.runs.detail(run_id).state

    def time_passes(self) -> None:
        """Every scheduled job falls due, and the dispatcher starts it."""
        with Session(self.db.engine) as session:
            for job in session.exec(select(Job).where(Job.state == JobState.scheduled)).all():
                job.run_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
                session.add(job)
            session.commit()
        self.jobs.dispatch_due()


@pytest.fixture
def lab():
    return _Lab()


def test_a_linear_run_goes_step_by_step_and_keeps_artifacts_by_name(lab):
    run = lab.start(lab.workflow({"ping": "ping", "check": "check"}, "start>ping ping>check check>end"))
    assert lab.keys() == ["ping"]
    lab.work("ping")
    assert lab.keys() == ["check"]
    lab.work("check")
    detail = lab.runs.detail(run)
    assert detail.state == JobState.succeeded and detail.finished_at is not None
    assert [(s.key, s.round, s.state) for s in detail.step_runs] == [
        ("ping", 1, JobState.succeeded),
        ("check", 1, JobState.succeeded),
    ]
    assert detail.step_runs[1].result.result == {"passed": True} and detail.step_runs[0].result is None
    artifacts = lab.runs.artifacts(run).artifacts
    assert artifacts["ping_up"].nodes == {"acc-1": True, "acc-2": True} and artifacts["ping_up"].step == "ping"
    assert list(lab.runs.artifacts(run, ["ping_up", "unknown"]).artifacts) == ["ping_up"]


def test_a_step_moves_on_once_when_its_last_node_finishes(lab):
    run = lab.start(lab.workflow({"ping": "ping", "check": "check"}, "start>ping ping>check"))
    lab.work("ping")
    lab.work("ping")  # nothing left to run, nothing moves twice
    assert [s.key for s in lab.runs.detail(run).step_runs] == ["ping", "check"]


def test_branches_run_in_parallel_and_a_join_waits_for_both(lab):
    lab.start(lab.workflow({"a": "ping", "b": "show", "j": "check"}, "start>a start>b a>j b>j j>end"))
    assert lab.keys() == ["a", "b"]
    lab.work("a")
    assert lab.keys() == ["b"]
    lab.work("b")
    assert lab.keys() == ["j"]


def test_a_condition_takes_one_side_and_a_join_past_it_doesnt_wait_for_the_other(lab):
    steps = {"up": "up", "yes": "check", "no": "show", "after": "check"}
    workflow = lab.workflow(steps, "start>up up>yes:true up>no:false yes>after no>after after>end")
    run = lab.start(workflow)
    lab.work("up", value=False)
    assert lab.keys() == ["no"]
    lab.work("no")
    assert lab.keys() == ["after"]
    assert lab.runs.detail(run).branches == {"up": "false"}


def test_a_wait_is_scheduled_and_the_backend_finishes_it_when_due(lab):
    run = lab.start(lab.workflow({"pause": "pause", "check": "check"}, "start>pause pause>check"))
    assert lab.keys() == [] and [j.data["key"] for j in lab.waiting(JobState.scheduled)] == ["pause"]
    step = lab.runs.detail(run).step_runs[0]
    assert step.state == JobState.scheduled and step.run_at is not None
    lab.jobs.dispatch_due()  # not due yet
    assert lab.keys() == []
    lab.time_passes()
    assert lab.keys() == ["check"]
    assert lab.runs.detail(run).step_runs[0].result.result == {"seconds": 30}


def test_stopping_a_run_cancels_its_wait(lab):
    run = lab.start(lab.workflow({"pause": "pause"}, "start>pause"))
    assert lab.runs.stop(run, stopped_by="bob").state == JobState.cancelled
    assert lab.waiting(JobState.scheduled) == []
    lab.time_passes()
    assert lab.state(run) == JobState.cancelled


def test_a_loop_goes_round_until_stopped(lab):
    run = lab.start(lab.workflow({"a": "ping", "b": "show"}, "start>a a>b b>a b>end"))
    assert lab.keys() == ["a"]
    lab.work("a")
    lab.work("b")
    assert lab.keys() == ["a"]
    assert [(s.key, s.round) for s in lab.runs.detail(run).step_runs][-1] == ("a", 2)
    stopped = lab.runs.stop(run, stopped_by="bob")
    assert stopped.state == JobState.cancelled and lab.keys() == []
    with pytest.raises(RunConflict):
        lab.runs.stop(run, stopped_by="bob")


def test_a_loop_fails_the_run_when_a_step_would_run_once_too_often(lab):
    run = lab.start(lab.workflow({"a": "check", "b": "check"}, "start>a a>b b>a", max_rounds=2))
    for _ in range(2):
        lab.work("a")
        lab.work("b")
    detail = lab.runs.detail(run)
    assert detail.state == JobState.failed
    assert detail.error == "Step a ran 2 times, as many as the workflow allows"
    assert lab.keys() == []


def test_a_failed_step_fails_the_run_and_stops_the_rest(lab):
    run = lab.start(lab.workflow({"a": "ping", "b": "show", "c": "check"}, "start>a start>b a>c b>c"))
    lab.work("a", fail_on=2)
    detail = lab.runs.detail(run)
    assert detail.state == JobState.failed
    assert detail.error == "Step a failed: on acc-2 of 2 nodes: unreachable"
    assert lab.keys() == []  # b was cancelled, c never started
    assert [s.state for s in detail.step_runs] == [JobState.failed, JobState.cancelled]
    responses = lab.runs.responses(run, detail.step_runs[0].job_id)
    assert [(r.hostname, r.state) for r in responses] == [("acc-1", JobState.succeeded), ("acc-2", JobState.failed)]


def test_evaluate_mode_pauses_after_each_step(lab):
    workflow = lab.workflow({"a": "ping", "b": "show", "c": "check"}, "start>a a>b b>c")
    run = lab.start(workflow, WorkflowRunMode.evaluate)
    lab.work("a")
    assert lab.state(run) == JobState.paused and lab.keys() == []
    assert lab.runs.detail(run).pending == ["a"]
    assert lab.runs.resume(run, to_end=False).state == JobState.running
    assert lab.keys() == ["b"]
    lab.work("b")
    assert lab.state(run) == JobState.paused
    lab.runs.resume(run, to_end=True)
    lab.work("c")
    assert lab.state(run) == JobState.succeeded
    with pytest.raises(RunConflict):
        lab.runs.resume(run, to_end=False)


def test_a_dry_run_shows_each_step_once_takes_both_sides_and_doesnt_wait(lab):
    steps = {"a": "ping", "up": "up", "pause": "pause", "b": "show"}
    workflow = lab.workflow(steps, "start>a a>up up>pause:true up>b:false pause>a b>end")
    run = lab.start(workflow, WorkflowRunMode.dry_run)
    lab.work("a")
    lab.work("up", value=None)
    assert lab.keys() == ["b"]
    lab.jobs.dispatch_due()  # a dry run's wait is due at once
    lab.work("b")
    assert lab.state(run) == JobState.succeeded


def test_a_run_needs_a_workflow_without_problems(lab):
    with pytest.raises(WorkflowRunError, match="Workflow: Nothing follows start"):
        lab.start(lab.workflow({"a": "ping"}, "a>end"))
    with pytest.raises(WorkflowRunError, match="a: Choose the nodes it runs on"):
        lab.start(lab.workflow({"a": "ping"}, "start>a", targets=()))


def test_runs_are_listed_per_workflow_and_only_finished_ones_deleted(lab):
    first = lab.workflow({"a": "check"}, "start>a")
    run = lab.start(first)
    lab.start(lab.workflow({"a": "check"}, "start>a"))
    assert [r.id for r in lab.runs.page(first, 50, 0).items] == [run]
    assert lab.runs.page(None, 50, 0).total == 2
    with pytest.raises(RunConflict):
        lab.runs.delete(run)
    lab.work("a")
    lab.runs.delete(run)
    assert lab.runs.page(first, 50, 0).total == 0
