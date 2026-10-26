"""Nested jobs: a workflow run (orchestrated, keeping its own state) holds step jobs, and a step that targets
nodes holds one job per node. States derive upward from the jobs that hold their own; cancel, delete and
purge reach every level."""

import pytest
from acex.jobs import JobConflict, JobManager, JobType, JobTypeRegistry
from acex.models.job import Job, JobState, JobSubjectType
from acex_devkit.models.job import JobUpdate
from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    def __init__(self, fail_for: set[int] = frozenset()):
        self.configured = True
        self.fail_for = fail_for
        self.published: list[int] = []

    def publish(self, job_type: str, job_id: int) -> None:
        if job_id in self.fail_for:
            raise ConnectionError("broker unreachable")
        self.published.append(job_id)


class _Node(BaseModel):
    node_id: int


class _Run(BaseModel):
    workflow_id: int


class _Step(BaseModel):
    step: str


RUN, NODE, STEP = "acex.operations.workflow", "acex.operations.execute", "acex.operations.workflow.parse"


def _registry() -> JobTypeRegistry:
    job_types = JobTypeRegistry()
    job_types.register(JobType(RUN, data=_Run, orchestrated=True))
    job_types.register(JobType(NODE, data=_Node, subject=(JobSubjectType.node, "node_id")))
    job_types.register(JobType(STEP, data=_Step))
    return job_types


class _Run3:
    """A run with a step over three nodes and a nodeless step."""

    def __init__(self, fail_for: set[int] = frozenset()):
        self.db = _Db()
        self.producer = _Producer(fail_for)
        self.jobs = JobManager(self.db, self.producer, _registry())
        self.finished: list[int] = []
        self.jobs.on_finished.append(lambda job: self.finished.append(job.id))
        self.run = self.jobs.open(RUN, {"workflow_id": 1}, created_by="alice")
        self.step = self.jobs.enqueue_batch(
            NODE, [{"node_id": n} for n in (1, 2, 3)], created_by="alice", parent_id=self.run.id
        )
        self.parse = self.jobs.enqueue(STEP, {"step": "find"}, created_by="alice", parent_id=self.run.id)
        self.nodes = [job.id for job in self.jobs.children(self.step.id)]

    def finish(self, job_id: int, state: JobState = JobState.succeeded) -> None:
        self.jobs.update(job_id, JobUpdate(state=JobState.running), worker="w")
        report = JobUpdate(state=state, error="boom") if state == JobState.failed else JobUpdate(state=state)
        self.jobs.update(job_id, report, worker="w")

    def ids(self) -> list[int]:
        with Session(self.db.engine) as session:
            return list(session.exec(select(Job.id).order_by(Job.id)).all())


@pytest.fixture
def run() -> _Run3:
    return _Run3()


def test_a_run_keeps_its_own_state_while_its_steps_derive_theirs(run):
    assert run.run.state == JobState.running
    run.finish(run.nodes[0])
    run.finish(run.nodes[1], JobState.failed)

    step = run.jobs.get(run.step.id)
    assert step.state == JobState.running  # one node job still queued
    assert step.children[JobState.failed] == 1

    run.finish(run.nodes[2])
    run.finish(run.parse.id)
    run_job = run.jobs.get(run.run.id)
    # The step derives failed; the run counts its steps by their derived states but keeps its own state.
    assert run_job.children[JobState.failed] == 1 and run_job.children[JobState.succeeded] == 1
    assert run_job.state == JobState.running

    run.jobs.set_state(run.run.id, JobState.paused)
    assert run.jobs.get(run.run.id).state == JobState.paused
    finished = run.jobs.set_state(run.run.id, JobState.failed, error="step failed")
    assert (finished.state, finished.error, finished.finished_at is not None) == (JobState.failed, "step failed", True)


def test_listing_shows_runs_with_their_own_state(run):
    run.jobs.set_state(run.run.id, JobState.paused)
    [listed] = run.jobs.list_jobs().items
    assert (listed.id, listed.state) == (run.run.id, JobState.paused)
    assert [job.id for job in run.jobs.list_jobs(state=JobState.paused).items] == [run.run.id]
    steps = run.jobs.children(run.run.id)
    assert [(job.id, job.state) for job in steps] == [(run.step.id, JobState.queued), (run.parse.id, JobState.queued)]


def test_finished_jobs_are_told_to_listeners(run):
    run.finish(run.nodes[0])
    run.finish(run.parse.id, JobState.failed)
    assert run.finished == [run.nodes[0], run.parse.id]


def test_a_failed_publish_is_told_to_listeners():
    run = _Run3(fail_for={4})  # ids: the run 1, the step 2, node jobs 3–5; node 2's job fails to publish
    assert 4 in run.finished


def test_parents_are_not_run_by_workers(run):
    with pytest.raises(JobConflict):
        run.jobs.update(run.step.id, JobUpdate(state=JobState.running), worker="w")


def test_cancelling_a_run_stops_every_job_under_it(run):
    run.finish(run.nodes[0])
    cancelled = run.jobs.cancel(run.run.id, cancelled_by="bob")

    assert cancelled.state == JobState.cancelled
    states = {job.id: job.state for job in run.jobs.children(run.step.id)}
    assert states == {
        run.nodes[0]: JobState.succeeded,
        run.nodes[1]: JobState.cancelled,
        run.nodes[2]: JobState.cancelled,
    }
    assert run.jobs.get(run.parse.id).state == JobState.cancelled


def test_deleting_a_run_deletes_every_job_under_it(run):
    other = run.jobs.enqueue(NODE, {"node_id": 9}, created_by="alice")
    run.jobs.delete(run.run.id)
    assert run.ids() == [other.id]


def test_purging_a_state_reaches_every_level_and_keeps_orchestrated_runs(run):
    for job in run.nodes:
        run.finish(job, JobState.failed)

    assert run.jobs.purge(JobState.failed) == 4  # three node jobs, then their emptied step
    assert run.ids() == [run.run.id, run.parse.id]

    run.jobs.set_state(run.run.id, JobState.cancelled)
    assert run.jobs.purge(JobState.cancelled) == 2  # the run, and the parse step under it
    assert run.ids() == []
