import logging

from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.jobs import InvalidJobResult, JobConflict, JobNotFound, JobPublishError, UnknownJobType
from acex.messaging import QUEUE_DURABLE, MessagingNotConfigured, queue_for
from acex_devkit.models.job import JobPurge, JobResponse, JobState, JobSubjectType, JobSummary, JobUpdate
from acex_devkit.models.pagination import PaginatedResponse
from acex_devkit.models.worker import (
    BrokerConnection,
    JobTypeInfo,
    QueueDeclaration,
    WorkerConnection,
    WorkerConnectRequest,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

logger = logging.getLogger("acex.api.workers")


def _worker(user: dict) -> str:
    """Who is reporting: the client id of a worker's service account, else the user."""
    return user.get("azp") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/workers", tags=["Workers"])
    jobs = automation_engine.jobs

    @router.post("/connect", response_model=WorkerConnection)
    def connect(request: WorkerConnectRequest):
        """Where a starting worker consumes from: the broker, and the queues that carry its job types.

        The answer holds the broker's password, which is why a worker has to
        authenticate to ask for it.
        """
        rabbitmq = automation_engine.settings.rabbitmq
        if not rabbitmq.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="RabbitMQ is not configured; set ACEX_RABBITMQ_HOST to run jobs.",
            )
        try:
            # Only job types the backend creates: a worker with code for any
            # other would start without error and never be sent a job.
            # Registered types always have a queue.
            queues = dict.fromkeys(queue_for(jobs.job_types.get(job_type).name) for job_type in request.job_types)
        except UnknownJobType as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        return WorkerConnection(
            broker=BrokerConnection(
                host=rabbitmq.host,
                port=rabbitmq.port,
                vhost=rabbitmq.vhost,
                user=rabbitmq.user,
                password=rabbitmq.password,
            ),
            queues=[QueueDeclaration(name=name, durable=QUEUE_DURABLE) for name in queues],
        )

    @router.get("/job_types", response_model=list[JobTypeInfo])
    def list_job_types():
        """Every job type the backend creates, and the queue that carries it."""
        return [JobTypeInfo(name=job_type.name, queue=queue_for(job_type.name)) for job_type in jobs.job_types]

    @router.get("/jobs", response_model=PaginatedResponse[JobSummary])
    def list_jobs(
        state: JobState | None = None,
        type: str | None = None,
        parent_id: int | None = Query(default=None, description="List a batch's jobs; without it, top-level jobs."),
        subject_type: JobSubjectType | None = None,
        subject_id: int | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        return jobs.list_jobs(
            state=state,
            type=type,
            parent_id=parent_id,
            subject_type=subject_type,
            subject_id=subject_id,
            limit=limit,
            offset=offset,
        )

    @router.get("/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: int):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No job {job_id}")
        return job

    @router.patch("/jobs/{job_id}", response_model=JobResponse)
    def report_on_job(job_id: int, report: JobUpdate, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """A worker claims a job (state running), then reports how it ended (succeeded or failed).

        409 means the job is not the worker's to run or report on, with the job
        as it stands; a worker that gets it on a claim acknowledges the message
        and skips the job. So does one that gets 404: the job has been deleted.
        """
        try:
            return jobs.update(job_id, report, worker=_worker(user))
        except JobNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except JobConflict as exc:
            raise _conflict(exc) from exc
        except InvalidJobResult as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(include_url=False, include_context=False),
            ) from exc

    @router.post("/jobs/{job_id}/requeue", response_model=JobResponse)
    def requeue_job(job_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Put a failed or cancelled job on its queue again, under the same id.

        A queued job is sent again, in case its message was lost. Running and
        succeeded jobs, and batch parents, answer 409.
        """
        try:
            job = jobs.requeue(job_id)
        except JobNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except JobConflict as exc:
            raise _conflict(exc) from exc
        except MessagingNotConfigured as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except JobPublishError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        logger.info(f"Job {job_id} ({job.type}) requeued by {user.get('sub') or 'anonymous'}")
        return job

    @router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
    def cancel_job(job_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Cancel a queued or running job, or a batch's unfinished jobs. Finished jobs answer 409."""
        who = user.get("sub") or "anonymous"
        try:
            job = jobs.cancel(job_id, cancelled_by=who)
        except JobNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except JobConflict as exc:
            raise _conflict(exc) from exc
        logger.info(f"Job {job_id} ({job.type}) cancelled by {who}")
        return job

    @router.delete("/jobs", response_model=JobPurge)
    def purge_jobs(state: JobState | None = None, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Delete every job, or with `state` every job in that state, to clean up. Jobs inside batches go too."""
        purged = JobPurge(deleted=jobs.purge(state))
        scope = f"{state} jobs" if state else "all jobs"
        logger.info(f"Purged {scope} ({purged.deleted}) by {user.get('sub') or 'anonymous'}")
        return purged

    @router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_job(job_id: int, user: dict = Depends(_auth.get_current_user)):  # noqa: B008
        """Delete a job in any state, or a batch with its jobs, to clean up. Cancel stops a job and keeps it.

        A worker still holding the job gets 404 on its next report.
        """
        try:
            jobs.delete(job_id)
        except JobNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        logger.info(f"Job {job_id} deleted by {user.get('sub') or 'anonymous'}")

    return router


def _conflict(exc: JobConflict) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"reason": str(exc), "job": exc.job.model_dump(mode="json")},
    )
