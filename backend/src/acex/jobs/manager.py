import logging
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from acex.jobs.registry import JobType, JobTypeRegistry, UnknownJobType, registry
from acex.messaging import JobProducer, MessagingNotConfigured
from acex.models.job import Job, JobResponse, JobState, JobSubjectType
from acex_devkit.models.job import JobSummary, JobUpdate
from acex_devkit.models.pagination import PaginatedResponse
from pydantic import BaseModel
from sqlalchemy import delete, or_, update
from sqlalchemy.orm import aliased
from sqlmodel import func, select

logger = logging.getLogger("acex.jobs")


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
    """A parent's state, from how many of the jobs under it are in each state."""
    total = sum(children.values())
    waiting = children[JobState.scheduled] + children[JobState.queued]
    if children[JobState.scheduled] == total:
        return JobState.scheduled
    if waiting == total:
        return JobState.queued
    if waiting or children[JobState.running]:
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

    Jobs nest: a batch's jobs run under it, and a batch may itself run under another job, e.g. a step of a
    workflow run. A parent's state is derived from the jobs under it, however deep, unless its job type is
    orchestrated: then whatever orchestrates it keeps its state.

    A job may be scheduled to run later: it waits in the table, not on a queue, until `dispatch_due` finds its
    time has come. A local job type is always scheduled, and run then by the backend itself.
    """

    def __init__(self, db_manager, producer: JobProducer, job_types: JobTypeRegistry = registry):
        self.db = db_manager
        self.producer = producer
        self.job_types = job_types
        #: Called with each job once it has finished: succeeded, failed, or failed to publish.
        self.on_finished: list[Callable[[JobResponse], None]] = []

    def enqueue(
        self,
        job_type: str,
        data: BaseModel | dict,
        *,
        created_by: str,
        parent_id: int | None = None,
        run_at: datetime | None = None,
    ) -> JobResponse:
        """Create a job, under `parent_id` if given, and publish it; or with `run_at`, or for a local job type,
        schedule it. Raises JobPublishError if it could not be published."""
        spec = self._spec(job_type)
        session = next(self.db.get_session())
        try:
            job = self._new_job(spec, data, created_by=created_by)
            job.parent_id = parent_id
            if run_at is not None or spec.local is not None:
                job.state = JobState.scheduled
                job.run_at = self._naive_utc(run_at or datetime.now(UTC))
            session.add(job)
            session.commit()
            session.refresh(job)
            if job.state == JobState.scheduled:
                return JobResponse.model_validate(job)
            if not self._publish(session, job):
                raise JobPublishError(JobResponse.model_validate(job))
            return JobResponse.model_validate(job)
        finally:
            session.close()

    def enqueue_batch(
        self,
        job_type: str,
        items: list[BaseModel | dict],
        *,
        created_by: str,
        request: BaseModel | None = None,
        parent_id: int | None = None,
    ) -> JobResponse:
        """Create one job per item under a parent, and publish them; the parent itself runs under
        `parent_id` if given.

        The parent stands for the request as a whole and is not queued itself; `request`, the batch as
        it was asked for, is kept as its data.
        A job that cannot be published is marked failed and the rest still go
        out, so the parent reports the outcome rather than this raising.
        """
        if not items:
            raise ValueError("A batch needs at least one job.")
        spec = self._spec(job_type)
        session = next(self.db.get_session())
        try:
            children = [self._new_job(spec, item, created_by=created_by) for item in items]
            data = request.model_dump(mode="json") if request is not None else None
            parent = Job(type=job_type, created_by=created_by, data=data, parent_id=parent_id)
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

    def open(self, job_type: str, data: BaseModel | dict, *, created_by: str) -> JobResponse:
        """Create an orchestrated parent, e.g. a workflow run: running from the start and never queued;
        whatever orchestrates it adds jobs under it and keeps its state with `set_state`."""
        spec = self._spec(job_type)
        if not spec.orchestrated:
            raise ValueError(f"Job type {job_type} is not orchestrated.")
        session = next(self.db.get_session())
        try:
            job = self._new_job(spec, data, created_by=created_by)
            job.state, job.started_at = JobState.running, datetime.now(UTC)
            session.add(job)
            session.commit()
            session.refresh(job)
            return self._response(session, job)
        finally:
            session.close()

    def dispatch_due(self, limit: int = 100) -> int:
        """Start the scheduled jobs whose time has come: queue and publish them, or run a local one here.
        Returns how many were started. Safe to call from several API processes at once: each job is taken by
        one of them (postgres SKIP LOCKED)."""
        now = self._naive_utc(datetime.now(UTC))
        session = next(self.db.get_session())
        try:
            due = session.exec(
                select(Job)
                .where(Job.state == JobState.scheduled, Job.run_at <= now)
                .order_by(Job.run_at, Job.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            local = []
            for job in due:
                spec = self.job_types.get(job.type)
                if spec.local is not None:
                    job.state, job.started_at, job.claimed_by = JobState.running, datetime.now(UTC), "backend"
                    local.append((job.id, spec))
                else:
                    job.state = JobState.queued
                session.add(job)
            session.commit()
            for job in due:
                session.refresh(job)
                if job.state == JobState.queued:
                    self._publish(session, job)
            for job_id, spec in local:
                self._run_local(session, session.get(Job, job_id), spec)
            return len(due)
        finally:
            session.close()

    def set_state(self, job_id: int, state: JobState, *, error: str | None = None) -> JobResponse:
        """Set an orchestrated parent's state; a finished state also stamps when it finished."""
        with self.locked(job_id) as job:
            if job is None:
                raise JobNotFound(f"No job {job_id}.")
            self.stamp(job, state, error=error)
        return self.get(job_id)

    @contextmanager
    def locked(self, job_id: int) -> Iterator[Job | None]:
        """An orchestrated parent's row, or None if it is gone, locked until the block ends so that only one
        caller at a time orchestrates it. What the block changes on the row is committed when it ends.

        The lock still lets jobs be added under the parent meanwhile (postgres FOR NO KEY UPDATE)."""
        session = next(self.db.get_session())
        try:
            job = session.exec(select(Job).where(Job.id == job_id).with_for_update(key_share=True)).first()
            if job is not None and not self._orchestrated(job.type):
                raise ValueError(f"Job {job_id} ({job.type}) keeps no state of its own to orchestrate.")
            yield job
            if job is not None:
                session.add(job)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def stamp(job: Job, state: JobState, *, error: str | None = None) -> None:
        """Set an orchestrated parent's state on its locked row; a finished state also stamps when."""
        job.state, job.error = state, error
        job.finished_at = None if state in (JobState.running, JobState.paused) else datetime.now(UTC)

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
        type_prefix: str | tuple[str, ...] | None = None,
        parent_id: int | None = None,
        subject_type: JobSubjectType | None = None,
        subject_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse[JobSummary]:
        """Jobs, newest first: the jobs under `parent_id`, otherwise the top-level ones.

        A parent's state is derived from its jobs, so filtering on `state` matches only jobs that hold their
        own state: jobs without jobs under them, and orchestrated parents.
        """
        filters = [Job.parent_id == parent_id if parent_id is not None else Job.parent_id.is_(None)]
        if state is not None:
            child = aliased(Job)
            has_children = select(child.id).where(child.parent_id == Job.id).exists()
            filters += [Job.state == state, ~has_children | Job.type.in_(self._orchestrated_types())]
        if type is not None:
            filters.append(Job.type == type)
        if type_prefix is not None:
            prefixes = (type_prefix,) if isinstance(type_prefix, str) else type_prefix
            filters.append(or_(*(Job.type.startswith(prefix) for prefix in prefixes)))
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
            ids = [job.id for job in jobs]
            counts = self._counts(session, ids)
            finished = self._finished_by_parent(session, ids) if counts else {}
            items = []
            for job in jobs:
                summary = JobSummary.model_validate(job)
                if job.id in counts:
                    self._as_batch(summary, job.type, counts[job.id], finished.get(job.id))
                items.append(summary)
            return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
        finally:
            session.close()

    def children(self, parent_id: int) -> list[JobResponse]:
        """The jobs directly under a parent in full, data and result included, oldest first. A job that is
        a parent itself carries its derived state and counts."""
        session = next(self.db.get_session())
        try:
            jobs = session.exec(select(Job).where(Job.parent_id == parent_id).order_by(Job.id)).all()
            counts = self._counts(session, [job.id for job in jobs])
            finished = self._finished_by_parent(session, list(counts))
            responses = []
            for job in jobs:
                response = JobResponse.model_validate(job)
                if job.id in counts:
                    self._as_batch(response, job.type, counts[job.id], finished.get(job.id))
                responses.append(response)
            return responses
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
            if self._has_children(session, job.id):
                raise JobConflict(self._response(session, job), "A parent is not run by a worker.")
            if report.state == JobState.running:
                self._claim(session, job, worker)
            else:
                self._finish(session, job, report, worker)
            session.refresh(job)
            response = self._response(session, job)
        finally:
            session.close()
        if report.state != JobState.running:
            self._finished(response)
        return response

    def requeue(self, job_id: int) -> JobResponse:
        """Put the job on its queue again, under the same id.

        A failed or cancelled job is queued again, keeping its attempts. A
        queued job only gets another message, for one that was lost: of two
        messages, the first claim wins and the other is skipped. Running and
        succeeded jobs, and batch parents, raise JobConflict.
        """
        if not self.producer.configured:
            raise MessagingNotConfigured("RabbitMQ is not configured; set ACEX_RABBITMQ_HOST to run jobs.")
        session = next(self.db.get_session())
        try:
            job = session.get(Job, job_id)
            if job is None:
                raise JobNotFound(f"No job {job_id}.")
            if self._has_children(session, job.id):
                raise JobConflict(self._response(session, job), "Requeue a batch's jobs one by one.")
            # Conditional, like a claim: of two requeues at once, only one resets the job.
            session.execute(
                update(Job)
                .where(Job.id == job.id, Job.state.in_([JobState.failed, JobState.cancelled]))
                .values(
                    state=JobState.queued,
                    claimed_by=None,
                    cancelled_by=None,
                    result=None,
                    error=None,
                    started_at=None,
                    finished_at=None,
                )
            )
            session.commit()
            session.refresh(job)
            if job.state != JobState.queued:
                raise JobConflict(self._response(session, job), f"Job {job.id} is {job.state}; it cannot be requeued.")
            if not self._publish(session, job):
                raise JobPublishError(JobResponse.model_validate(job))
            return self._response(session, job)
        finally:
            session.close()

    def cancel(self, job_id: int, *, cancelled_by: str) -> JobResponse:
        """Stop a queued or running job, or every such job under a parent however deep, and an orchestrated
        parent itself; the jobs stay as a record.

        A message still on its queue is skipped at its claim, and a worker
        still running the job gets 409 when it reports. Raises JobConflict
        when there is nothing left to cancel.
        """
        session = next(self.db.get_session())
        try:
            job = session.get(Job, job_id)
            if job is None:
                raise JobNotFound(f"No job {job_id}.")
            # Jobs that hold their own state: those with nothing under them, and orchestrated parents.
            own_state = self._own_state(session, self._subtree(session, job.id))
            # Conditional, so a job that finishes meanwhile keeps its outcome.
            cancelled = session.execute(
                update(Job)
                .where(
                    Job.id.in_(own_state),
                    Job.state.in_([JobState.scheduled, JobState.queued, JobState.running, JobState.paused]),
                )
                .values(state=JobState.cancelled, cancelled_by=cancelled_by, finished_at=datetime.now(UTC))
            )
            session.commit()
            session.refresh(job)
            if not cancelled.rowcount:
                response = self._response(session, job)
                raise JobConflict(response, f"Job {job.id} is {response.state}; there is nothing to cancel.")
            return self._response(session, job)
        finally:
            session.close()

    def delete(self, job_id: int) -> None:
        """Delete a job in any state, with every job under it however deep.

        A message still on its queue, or a worker still running the job, gets
        404 on its next report and skips the job. Discoveries a job recorded
        are kept, without their job.
        """
        session = next(self.db.get_session())
        try:
            if session.get(Job, job_id) is None:
                raise JobNotFound(f"No job {job_id}.")
            # Every job explicitly: SQLite enforces no ON DELETE CASCADE by default.
            session.execute(delete(Job).where(Job.id.in_(self._subtree(session, job_id))))
            session.commit()
        finally:
            session.close()

    def purge(self, state: JobState | None = None) -> int:
        """Delete every job, or every job in `state`, and return how many were deleted.

        With a state, the jobs that hold their own state go: jobs inside batches, and orchestrated parents
        with everything under them. A derived parent goes once no jobs are left under it.
        """
        session = next(self.db.get_session())
        try:
            if state is None:
                deleted = session.execute(delete(Job)).rowcount
            else:
                child = aliased(Job)
                has_children = select(child.id).where(child.parent_id == Job.id).exists()
                orchestrated = self._orchestrated_types()
                leaves = session.exec(select(Job.id).where(Job.state == state, ~has_children)).all()
                runs = session.exec(select(Job.id).where(Job.state == state, Job.type.in_(orchestrated))).all()
                doomed = set(leaves).union(*(self._subtree(session, run) for run in runs))
                deleted = 0
                while doomed:
                    parents = session.exec(
                        select(Job.parent_id).where(Job.id.in_(doomed), Job.parent_id.is_not(None)).distinct()
                    ).all()
                    deleted += session.execute(delete(Job).where(Job.id.in_(doomed))).rowcount
                    doomed = set(
                        session.exec(
                            select(Job.id).where(Job.id.in_(parents), ~has_children, Job.type.not_in(orchestrated))
                        ).all()
                    )
            session.commit()
            return deleted
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
            self._finished(JobResponse.model_validate(job))
            return False
        return True

    def _run_local(self, session, job: Job, spec: JobType) -> None:
        """Run a local job the backend has taken, and finish it as a worker would: unless it was cancelled
        meanwhile."""
        try:
            outcome = spec.local(JobResponse.model_validate(job))
            values = {"state": JobState.succeeded, "result": self._valid_result(spec, self._as_dict(outcome))}
        except Exception as exc:
            logger.exception(f"Local job {job.id} ({job.type}) failed")
            values = {"state": JobState.failed, "error": f"{type(exc).__name__}: {exc}"}
        finished = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.state == JobState.running)
            .values(**values, finished_at=datetime.now(UTC))
        )
        session.commit()
        if finished.rowcount == 1:
            session.refresh(job)
            self._finished(JobResponse.model_validate(job))

    @staticmethod
    def _as_dict(result: BaseModel | None) -> dict | None:
        return result.model_dump(mode="json") if result is not None else None

    @staticmethod
    def _naive_utc(moment: datetime) -> datetime:
        return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment

    def _finished(self, job: JobResponse) -> None:
        # The job's outcome is already saved: a listener that fails doesn't undo it, nor fail the report.
        for listener in self.on_finished:
            try:
                listener(job)
            except Exception:
                logger.exception(f"Listener {listener!r} failed on job {job.id} ({job.type})")

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
        spec = self.job_types.get(job.type)
        result = self._valid_result(spec, report.result) if report.state == JobState.succeeded else None
        finished = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.state == JobState.running, Job.claimed_by == worker)
            .values(state=report.state, result=result, error=report.error, finished_at=datetime.now(UTC))
        )
        try:
            if finished.rowcount == 1 and report.state == JobState.succeeded and spec.on_succeeded is not None:
                spec.on_succeeded(session, job, spec.result.model_validate(result) if result is not None else None)
            session.commit()
        except Exception:
            session.rollback()
            raise
        if finished.rowcount != 1:
            session.refresh(job)
            if job.state == JobState.running:
                reason = f"Job {job.id} is claimed by {job.claimed_by}, not {worker}."
            else:
                reason = f"Job {job.id} is {job.state}, not running."
            raise JobConflict(self._response(session, job), reason)

    def _valid_result(self, spec: JobType, result: dict | None) -> dict | None:
        if spec.result is None:
            if result is not None:
                raise InvalidJobResult(f"Job type {spec.name} gives no result.")
            return None
        if result is None:
            raise InvalidJobResult(f"Job type {spec.name} needs a result.")
        return spec.result.model_validate(result).model_dump(mode="json")

    def _orchestrated(self, job_type: str) -> bool:
        try:
            return self.job_types.get(job_type).orchestrated
        except UnknownJobType:
            return False

    def _orchestrated_types(self) -> list[str]:
        return [job_type.name for job_type in self.job_types if job_type.orchestrated]

    def _has_children(self, session, job_id: int) -> bool:
        return session.exec(select(Job.id).where(Job.parent_id == job_id).limit(1)).first() is not None

    def _subtree(self, session, job_id: int) -> list[int]:
        """The job and every job under it, however deep."""
        ids, level = [job_id], [job_id]
        while level:
            level = session.exec(select(Job.id).where(Job.parent_id.in_(level))).all()
            ids += level
        return ids

    def _own_state(self, session, job_ids: list[int]) -> list[int]:
        """Of `job_ids`, those that hold their own state: no jobs under them, or an orchestrated type."""
        parents = set(session.exec(select(Job.parent_id).where(Job.parent_id.in_(job_ids))).all())
        rows = session.exec(select(Job.id, Job.type).where(Job.id.in_(job_ids))).all()
        return [job_id for job_id, job_type in rows if job_id not in parents or self._orchestrated(job_type)]

    def _counts(self, session, job_ids: list[int]) -> dict[int, Counter]:
        """For each of `job_ids` with jobs under it, how many of those are in each state: a job's own state,
        or for a derived parent the state derived from its jobs, however deep."""
        if not job_ids:
            return {}
        rows = session.exec(select(Job.id, Job.parent_id, Job.state, Job.type).where(Job.parent_id.in_(job_ids))).all()
        deeper = self._counts(session, [row[0] for row in rows])
        counts: dict[int, Counter] = {}
        for job_id, parent_id, state, job_type in rows:
            if job_id in deeper and not self._orchestrated(job_type):
                state = derive_state(deeper[job_id])
            counts.setdefault(parent_id, Counter())[JobState(state)] += 1
        return counts

    def _finished_by_parent(self, session, job_ids: list[int]) -> dict[int, datetime]:
        if not job_ids:
            return {}
        rows = session.exec(
            select(Job.parent_id, func.max(Job.finished_at)).where(Job.parent_id.in_(job_ids)).group_by(Job.parent_id)
        ).all()
        return {parent_id: finished_at for parent_id, finished_at in rows if finished_at is not None}

    def _as_batch(
        self, item: JobResponse | JobSummary, job_type: str, children: Counter, finished_at: datetime | None
    ) -> None:
        """Give a parent what is derived from its jobs: their counts and, unless it is orchestrated, its state
        and once every one has finished, when the last one did."""
        item.children = {state: children[state] for state in JobState}
        if self._orchestrated(job_type):
            return
        item.state = derive_state(children)
        waiting = (JobState.scheduled, JobState.queued, JobState.running)
        item.finished_at = None if item.state in waiting else finished_at

    def _response(self, session, job: Job) -> JobResponse:
        response = JobResponse.model_validate(job)
        children = self._counts(session, [job.id]).get(job.id)
        if children:
            self._as_batch(response, job.type, children, self._finished_by_parent(session, [job.id]).get(job.id))
        return response
