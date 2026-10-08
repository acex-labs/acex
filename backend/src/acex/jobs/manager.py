from collections import Counter
from datetime import UTC, datetime

from acex.jobs.registry import JobType, JobTypeRegistry, registry
from acex.messaging import JobProducer, MessagingNotConfigured
from acex.models.job import Job, JobResponse, JobState, JobSubjectType
from acex_devkit.models.job import JobSummary, JobUpdate
from acex_devkit.models.pagination import PaginatedResponse
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import aliased
from sqlmodel import func, select


class JobPublishError(RuntimeError):
    """The job was saved but could not be put on its queue; it is marked failed."""

    def __init__(self, job: JobResponse):
        super().__init__(f"Job {job.id} ({job.type}): {job.error}")
        self.job = job


class JobNotFound(LookupError):
    pass


class JobConflict(RuntimeError):
    """A worker's report does not fit the job's state; `job` is how it stands now."""

    def __init__(self, job: JobResponse, reason: str):
        super().__init__(reason)
        self.job = job


class InvalidJobResult(ValueError):
    pass


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

    def list_jobs(
        self,
        *,
        state: JobState | None = None,
        type: str | None = None,
        parent_id: int | None = None,
        subject_type: JobSubjectType | None = None,
        subject_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[JobSummary]:
        """Jobs, newest first: the jobs of a batch given its `parent_id`, otherwise the top-level ones.

        A batch parent's state is derived from its jobs, so filtering on
        `state` matches only jobs that hold their own state, not parents.
        """
        filters = [Job.parent_id == parent_id if parent_id is not None else Job.parent_id.is_(None)]
        if state is not None:
            child = aliased(Job)
            has_children = select(child.id).where(child.parent_id == Job.id).exists()
            filters += [Job.state == state, ~has_children]
        if type is not None:
            filters.append(Job.type == type)
        if subject_type is not None:
            filters.append(Job.subject_type == subject_type)
        if subject_id is not None:
            filters.append(Job.subject_id == subject_id)

        session = next(self.db.get_session())
        try:
            total = session.exec(select(func.count()).select_from(Job).where(*filters)).one()
            jobs = session.exec(
                select(Job).where(*filters).order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit)
            ).all()
            counts = self._children_by_parent(session, [job.id for job in jobs])
            items = []
            for job in jobs:
                summary = JobSummary.model_validate(job)
                if job.id in counts:
                    summary.children = {each: counts[job.id][each] for each in JobState}
                    summary.state = derive_state(counts[job.id])
                items.append(summary)
            return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
        finally:
            session.close()

    def update(self, job_id: int, report: JobUpdate, *, worker: str) -> JobResponse:
        """Apply a worker's report: a claim (running), or how the job ended.

        Raises JobNotFound, JobConflict when the report does not fit the job's
        state, and InvalidJobResult when a result does not fit its job type. A
        report that repeats one already applied is answered as if it were new,
        so a worker can safely resend one whose answer it never got.
        """
        session = next(self.db.get_session())
        try:
            job = session.get(Job, job_id)
            if job is None:
                raise JobNotFound(f"No job {job_id}.")
            if self._children_by_parent(session, [job.id]):
                raise JobConflict(self._response(session, job), "A batch's parent is not run by a worker.")
            if report.state == JobState.running:
                self._claim(session, job, worker)
            else:
                self._finish(session, job, report, worker)
            session.refresh(job)
            return self._response(session, job)
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
            # The type matters: a KeyError's message is just the missing key.
            job.error = f"Could not be published: {type(exc).__name__}: {exc}"
            job.finished_at = datetime.now(UTC)
            session.add(job)
            session.commit()
            session.refresh(job)
            return False
        return True

    def _claim(self, session, job: Job, worker: str) -> None:
        if job.state == JobState.running and job.claimed_by == worker:
            return
        # Only a queued job can be claimed, and the condition is in the UPDATE
        # itself: of two workers claiming at once, exactly one gets the job. A
        # job redelivered after its worker died stays with that worker and is
        # found later by how long it has been running.
        claimed = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.state == JobState.queued)
            .values(
                state=JobState.running,
                attempts=Job.attempts + 1,
                started_at=datetime.now(UTC),
                claimed_by=worker,
            )
        )
        session.commit()
        if claimed.rowcount != 1:
            session.refresh(job)
            reason = f"Job {job.id} is {job.state}" + (f", claimed by {job.claimed_by}." if job.claimed_by else ".")
            raise JobConflict(self._response(session, job), reason)

    def _finish(self, session, job: Job, report: JobUpdate, worker: str) -> None:
        if job.state == report.state and job.claimed_by == worker:
            return
        result = self._valid_result(job.type, report.result) if report.state == JobState.succeeded else None
        finished = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.state == JobState.running, Job.claimed_by == worker)
            .values(state=report.state, result=result, error=report.error, finished_at=datetime.now(UTC))
        )
        session.commit()
        if finished.rowcount != 1:
            session.refresh(job)
            if job.state == JobState.running:
                reason = f"Job {job.id} is claimed by {job.claimed_by}, not {worker}."
            else:
                reason = f"Job {job.id} is {job.state}, not running."
            raise JobConflict(self._response(session, job), reason)

    def _valid_result(self, job_type: str, result: dict | None) -> dict | None:
        spec = self.job_types.get(job_type)
        if spec.result is None:
            if result is not None:
                raise InvalidJobResult(f"Job type {job_type} gives no result.")
            return None
        if result is None:
            raise InvalidJobResult(f"Job type {job_type} needs a result.")
        return spec.result.model_validate(result).model_dump(mode="json")

    def _children_by_parent(self, session, job_ids: list[int]) -> dict[int, Counter]:
        if not job_ids:
            return {}
        rows = session.exec(
            select(Job.parent_id, Job.state, func.count())
            .where(Job.parent_id.in_(job_ids))
            .group_by(Job.parent_id, Job.state)
        ).all()
        counts: dict[int, Counter] = {}
        for parent_id, state, count in rows:
            counts.setdefault(parent_id, Counter())[JobState(state)] = count
        return counts

    def _response(self, session, job: Job) -> JobResponse:
        response = JobResponse.model_validate(job)
        children = self._children_by_parent(session, [job.id]).get(job.id)
        if children:
            response.children = {state: children[state] for state in JobState}
            response.state = derive_state(children)
        return response
