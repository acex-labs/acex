from collections import Counter
from datetime import UTC, datetime

from acex.jobs.registry import JobType, JobTypeRegistry, registry
from acex.messaging import JobProducer, MessagingNotConfigured
from acex.models.job import Job, JobResponse, JobState
from pydantic import BaseModel
from sqlmodel import func, select


class JobPublishError(RuntimeError):
    """The job was saved but could not be put on its queue; it is marked failed."""

    def __init__(self, job: JobResponse):
        super().__init__(f"Job {job.id} ({job.type}) could not be published: {job.error}")
        self.job = job


def derive_state(children: Counter) -> JobState:
    """A batch parent's state, from how many of its jobs are in each state."""
    total = sum(children.values())
    if children[JobState.queued] == total:
        return JobState.queued
    if children[JobState.queued] or children[JobState.running]:
        return JobState.running
    if children[JobState.failed]:
        return JobState.failed
    if children[JobState.succeeded]:
        return JobState.succeeded
    return JobState.cancelled


class JobManager:
    """Creates jobs and puts them on their queues.

    A job is committed before it is published, so a worker never receives an
    id the API does not know yet. A job whose publish fails is marked failed;
    one that is lost on the way is found later by its age in the jobs table.
    """

    def __init__(self, db_manager, producer: JobProducer, job_types: JobTypeRegistry = registry):
        self.db = db_manager
        self.producer = producer
        self.job_types = job_types

    def enqueue(self, job_type: str, data: BaseModel | dict, *, created_by: str) -> JobResponse:
        """Create a job and publish it. Raises JobPublishError if it could not be published."""
        spec = self._spec(job_type)
        session = next(self.db.get_session())
        try:
            job = self._new_job(spec, data, created_by=created_by)
            session.add(job)
            session.commit()
            session.refresh(job)
            if not self._publish(session, job):
                raise JobPublishError(JobResponse.model_validate(job))
            return JobResponse.model_validate(job)
        finally:
            session.close()

    def enqueue_batch(self, job_type: str, items: list[BaseModel | dict], *, created_by: str) -> JobResponse:
        """Create one job per item under a parent, and publish them.

        The parent stands for the request as a whole and is not queued itself.
        A job that cannot be published is marked failed and the rest still go
        out, so the parent reports the outcome rather than this raising.
        """
        if not items:
            raise ValueError("A batch needs at least one job.")
        spec = self._spec(job_type)
        session = next(self.db.get_session())
        try:
            children = [self._new_job(spec, item, created_by=created_by) for item in items]
            parent = Job(type=job_type, created_by=created_by)
            session.add(parent)
            session.flush()
            for child in children:
                child.parent_id = parent.id
            session.add_all(children)
            session.commit()
            for child in children:
                session.refresh(child)
                self._publish(session, child)
            return self._response(session, parent)
        finally:
            session.close()

    def get(self, job_id: int) -> JobResponse | None:
        session = next(self.db.get_session())
        try:
            job = session.get(Job, job_id)
            return self._response(session, job) if job is not None else None
        finally:
            session.close()

    def _spec(self, job_type: str) -> JobType:
        spec = self.job_types.get(job_type)
        # Checked before anything is saved, so an unconfigured broker leaves no
        # jobs behind that nothing will ever run.
        if not self.producer.configured:
            raise MessagingNotConfigured("RabbitMQ is not configured; set ACEX_RABBITMQ_HOST to run jobs.")
        return spec

    def _new_job(self, spec: JobType, data: BaseModel | dict, *, created_by: str) -> Job:
        validated = spec.data.model_validate(data)
        subject_type, subject_id = None, None
        if spec.subject is not None:
            subject_type, field = spec.subject
            subject_id = getattr(validated, field)
        return Job(
            type=spec.name,
            data=validated.model_dump(mode="json"),
            subject_type=subject_type,
            subject_id=subject_id,
            created_by=created_by,
        )

    def _publish(self, session, job: Job) -> bool:
        try:
            self.producer.publish(job.type, job.id)
        except Exception as exc:
            job.state = JobState.failed
            job.error = f"Could not be published: {exc}"
            job.finished_at = datetime.now(UTC)
            session.add(job)
            session.commit()
            session.refresh(job)
            return False
        return True

    def _response(self, session, job: Job) -> JobResponse:
        response = JobResponse.model_validate(job)
        rows = session.exec(select(Job.state, func.count()).where(Job.parent_id == job.id).group_by(Job.state)).all()
        if rows:
            children = Counter({JobState(state): count for state, count in rows})
            response.children = {state: children[state] for state in JobState}
            response.state = derive_state(children)
        return response
