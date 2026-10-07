"""Jobs: a job is saved before it is published, carries only ids, and a failed
publish leaves it marked failed rather than silently queued."""

from collections import Counter

import pytest
from acex.jobs import JobManager, JobPublishError, JobType, JobTypeRegistry, UnknownJobType, derive_state
from acex.messaging import JobProducer, MessagingNotConfigured, UnroutedJobType, queue_for
from acex.models.job import Job, JobState, JobSubjectType
from acex.settings import RabbitMQSettings
from pydantic import BaseModel, ValidationError
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
    """Stub: records what is published; fails for the job ids in `fail_for`."""

    def __init__(self, configured: bool = True, fail_for: set[int] = frozenset()):
        self.configured = configured
        self.fail_for = fail_for
        self.published: list[tuple[str, int]] = []

    def publish(self, job_type: str, job_id: int) -> None:
        if job_id in self.fail_for:
            raise ConnectionError("broker unreachable")
        self.published.append((job_type, job_id))


class _Discover(BaseModel):
    node_id: int


class _NoSubject(BaseModel):
    pass


def _registry() -> JobTypeRegistry:
    job_types = JobTypeRegistry()
    job_types.register(JobType("acex.ztp.discover", data=_Discover, subject=(JobSubjectType.node, "node_id")))
    return job_types


@pytest.fixture
def db():
    return _Db()


def _jobs(db) -> list[Job]:
    with Session(db.engine) as session:
        return list(session.exec(select(Job).order_by(Job.id)).all())


class TestRouting:
    def should_route_a_flow_to_its_queue(self):
        assert queue_for("acex.ztp.discover") == "acex.ztp"
        assert queue_for("acex.ztp.provision") == "acex.ztp"

    def should_refuse_a_job_type_no_queue_carries(self):
        with pytest.raises(UnroutedJobType):
            queue_for("acex.nothing.here")


class TestProducer:
    def should_build_no_app_without_a_broker(self):
        producer = JobProducer(RabbitMQSettings())
        assert not producer.configured
        with pytest.raises(MessagingNotConfigured):
            producer.publish("acex.ztp.discover", 1)

    def should_connect_where_settings_say(self):
        settings = RabbitMQSettings(host="rabbitmq", user="acex", password="pw")
        assert JobProducer(settings)._app.conf.broker_url == settings.url

    def should_declare_durable_queues(self):
        # Workers declare the same queues; RabbitMQ refuses a second declaration
        # with different arguments, so this is part of the contract with them.
        [queue] = JobProducer(RabbitMQSettings(host="rabbitmq"))._app.conf.task_queues
        assert (queue.name, queue.durable, queue.queue_arguments) == ("acex.ztp", True, None)

    def should_send_the_job_id_to_its_queue(self, monkeypatch):
        sent = []
        producer = JobProducer(RabbitMQSettings(host="rabbitmq"))
        monkeypatch.setattr(producer._app, "send_task", lambda name, **kwargs: sent.append((name, kwargs)))
        producer.publish("acex.ztp.discover", 42)
        assert sent == [("acex.ztp.discover", {"args": [42], "task_id": "42", "queue": "acex.ztp"})]


class TestRegistry:
    def should_refuse_a_job_type_no_queue_carries(self):
        with pytest.raises(UnroutedJobType):
            JobTypeRegistry().register(JobType("acex.nothing.here", data=_NoSubject))

    def should_refuse_a_subject_field_the_data_lacks(self):
        with pytest.raises(ValueError, match="node_id"):
            JobTypeRegistry().register(
                JobType("acex.ztp.discover", data=_NoSubject, subject=(JobSubjectType.node, "node_id"))
            )

    def should_refuse_registering_a_job_type_twice(self):
        job_types = _registry()
        with pytest.raises(ValueError, match="already registered"):
            job_types.register(JobType("acex.ztp.discover", data=_Discover))

    def should_refuse_an_unknown_job_type(self):
        with pytest.raises(UnknownJobType):
            _registry().get("acex.ztp.unknown")


class TestEnqueue:
    def should_save_the_job_before_publishing_its_id(self, db):
        producer = _Producer()
        job = JobManager(db, producer, _registry()).enqueue("acex.ztp.discover", {"node_id": 7}, created_by="alice")
        assert producer.published == [("acex.ztp.discover", job.id)]
        [saved] = _jobs(db)
        assert (saved.id, saved.state, saved.data, saved.created_by) == (
            job.id,
            JobState.queued,
            {"node_id": 7},
            "alice",
        )

    def should_derive_the_subject_from_the_data(self, db):
        job = JobManager(db, _Producer(), _registry()).enqueue(
            "acex.ztp.discover", _Discover(node_id=7), created_by="a"
        )
        assert (job.subject_type, job.subject_id) == (JobSubjectType.node, 7)

    def should_reject_data_that_does_not_fit_the_job_type(self, db):
        with pytest.raises(ValidationError):
            JobManager(db, _Producer(), _registry()).enqueue("acex.ztp.discover", {"node": 7}, created_by="a")
        assert _jobs(db) == []

    def should_save_nothing_without_a_broker(self, db):
        with pytest.raises(MessagingNotConfigured):
            JobManager(db, _Producer(configured=False), _registry()).enqueue(
                "acex.ztp.discover", {"node_id": 7}, created_by="a"
            )
        assert _jobs(db) == []

    def should_mark_a_job_failed_when_it_cannot_be_published(self, db):
        with pytest.raises(JobPublishError) as exc:
            JobManager(db, _Producer(fail_for={1}), _registry()).enqueue(
                "acex.ztp.discover", {"node_id": 7}, created_by="a"
            )
        [saved] = _jobs(db)
        assert saved.state == JobState.failed
        assert "broker unreachable" in saved.error
        assert saved.finished_at is not None
        assert exc.value.job.state == JobState.failed


class TestBatch:
    def should_create_one_job_per_item_under_a_parent(self, db):
        producer = _Producer()
        parent = JobManager(db, producer, _registry()).enqueue_batch(
            "acex.ztp.discover", [{"node_id": n} for n in (1, 2, 3)], created_by="a"
        )
        children = [job for job in _jobs(db) if job.parent_id == parent.id]
        assert [job.subject_id for job in children] == [1, 2, 3]
        assert producer.published == [("acex.ztp.discover", job.id) for job in children]
        assert parent.state == JobState.queued
        assert parent.children[JobState.queued] == 3

    def should_not_queue_the_parent(self, db):
        producer = _Producer()
        parent = JobManager(db, producer, _registry()).enqueue_batch(
            "acex.ztp.discover", [{"node_id": 1}], created_by="a"
        )
        assert parent.id not in [job_id for _, job_id in producer.published]

    def should_still_publish_the_rest_when_one_fails(self, db):
        # Ids: parent 1, children 2-4; the second child fails to publish.
        producer = _Producer(fail_for={3})
        parent = JobManager(db, producer, _registry()).enqueue_batch(
            "acex.ztp.discover", [{"node_id": n} for n in (1, 2, 3)], created_by="a"
        )
        assert [job_id for _, job_id in producer.published] == [2, 4]
        assert parent.children[JobState.failed] == 1
        assert parent.children[JobState.queued] == 2
        assert parent.state == JobState.running

    def should_refuse_an_empty_batch(self, db):
        with pytest.raises(ValueError):
            JobManager(db, _Producer(), _registry()).enqueue_batch("acex.ztp.discover", [], created_by="a")


class TestDerivedState:
    @pytest.mark.parametrize(
        ("children", "state"),
        [
            ({JobState.queued: 3}, JobState.queued),
            ({JobState.queued: 2, JobState.succeeded: 1}, JobState.running),
            ({JobState.running: 1, JobState.failed: 2}, JobState.running),
            ({JobState.succeeded: 2, JobState.failed: 1}, JobState.failed),
            ({JobState.succeeded: 3}, JobState.succeeded),
            ({JobState.succeeded: 1, JobState.cancelled: 2}, JobState.succeeded),
            ({JobState.cancelled: 3}, JobState.cancelled),
        ],
    )
    def should_follow_its_jobs(self, children, state):
        assert derive_state(Counter(children)) == state

    def should_report_a_plain_job_as_stored(self, db):
        manager = JobManager(db, _Producer(), _registry())
        job = manager.enqueue("acex.ztp.discover", {"node_id": 7}, created_by="a")
        assert manager.get(job.id).children is None
        assert manager.get(9999) is None
