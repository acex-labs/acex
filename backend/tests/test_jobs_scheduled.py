"""Scheduled jobs wait in the jobs table, not on a queue, until they fall due: then a worker's job is queued
and published, and a local job is run by the backend itself. Either can be cancelled while it waits."""

from datetime import UTC, datetime, timedelta

import pytest
from acex.jobs import JobManager, JobType, JobTypeRegistry
from acex.models.job import Job, JobState
from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


class _Db:
    def __init__(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session


class _Producer:
    configured = True

    def __init__(self):
        self.published: list[int] = []

    def publish(self, job_type: str, job_id: int) -> None:
        self.published.append(job_id)


class _Data(BaseModel):
    n: int


class _Result(BaseModel):
    doubled: int


class _Doubler:
    @staticmethod
    def run(job) -> _Result:
        if job.data["n"] < 0:
            raise ValueError("no negatives")
        return _Result(doubled=job.data["n"] * 2)


REMOTE, LOCAL = "acex.operations.remote", "acex.operations.local"


class _Lab:
    def __init__(self):
        self.db = _Db()
        self.producer = _Producer()
        job_types = JobTypeRegistry()
        job_types.register(JobType(REMOTE, data=_Data))
        job_types.register(JobType(LOCAL, data=_Data, result=_Result, local=_Doubler.run))
        self.jobs = JobManager(self.db, self.producer, job_types)
        self.finished: list[int] = []
        self.jobs.on_finished.append(lambda job: self.finished.append(job.id))

    def fall_due(self, job_id: int) -> None:
        with Session(self.db.engine) as session:
            job = session.get(Job, job_id)
            job.run_at = datetime.now(UTC) - timedelta(seconds=1)
            session.add(job)
            session.commit()


@pytest.fixture
def lab():
    return _Lab()


def test_a_job_scheduled_for_later_is_published_when_due(lab):
    later = datetime.now(UTC) + timedelta(hours=1)
    job = lab.jobs.enqueue(REMOTE, {"n": 1}, created_by="alice", run_at=later)
    assert job.state == JobState.scheduled and lab.producer.published == []
    assert lab.jobs.dispatch_due() == 0
    lab.fall_due(job.id)
    assert lab.jobs.dispatch_due() == 1
    assert lab.jobs.get(job.id).state == JobState.queued and lab.producer.published == [job.id]
    assert lab.jobs.dispatch_due() == 0  # started once


def test_a_local_job_is_run_by_the_backend_when_due(lab):
    job = lab.jobs.enqueue(LOCAL, {"n": 21}, created_by="alice")
    assert job.state == JobState.scheduled  # due now, started on the dispatcher's next look
    lab.jobs.dispatch_due()
    done = lab.jobs.get(job.id)
    assert done.state == JobState.succeeded and done.result == {"doubled": 42} and done.claimed_by == "backend"
    assert lab.finished == [job.id] and lab.producer.published == []
    failing = lab.jobs.enqueue(LOCAL, {"n": -1}, created_by="alice")
    lab.jobs.dispatch_due()
    assert lab.jobs.get(failing.id).error == "ValueError: no negatives"


def test_a_scheduled_job_can_be_cancelled_before_it_falls_due(lab):
    job = lab.jobs.enqueue(LOCAL, {"n": 1}, created_by="alice", run_at=datetime.now(UTC) + timedelta(minutes=5))
    assert lab.jobs.cancel(job.id, cancelled_by="bob").state == JobState.cancelled
    lab.fall_due(job.id)
    assert lab.jobs.dispatch_due() == 0 and lab.finished == []
