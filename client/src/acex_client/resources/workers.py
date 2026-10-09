"""Workers — `/workers/*`: how a worker finds its broker, and the jobs it runs."""

from __future__ import annotations

from acex_devkit.models.job import JobResponse, JobState, JobSummary, JobUpdate
from acex_devkit.models.worker import JobTypeInfo, WorkerConnection, WorkerConnectRequest
from pydantic import BaseModel

from acex_client.http import RestClient
from acex_client.resources.base import ActionMixin, ListMixin, Resource, action


class Jobs(Resource, ListMixin, ActionMixin):
    """Jobs — `/workers/jobs`. `query()` lists summaries; `get()` one job in full.

    A worker claims a job before running it, then reports how it ended. A
    claim or report that does not fit the job's state raises AcexConflictError.
    """

    path = "/workers/jobs"
    response_model = JobResponse  # type: ignore
    list_model = JobSummary  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "{job_id}")
    def get(self, job_id: int) -> JobResponse: ...

    @action("PATCH", "{job_id}")
    def report(self, job_id: int, payload: JobUpdate) -> JobResponse: ...

    def claim(self, job_id: int) -> JobResponse:
        """Take the job. Its data comes back with it."""
        return self.report(job_id=job_id, payload=JobUpdate(state=JobState.running))

    def succeed(self, job_id: int, result: BaseModel | dict | None = None) -> JobResponse:
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="json")
        return self.report(job_id=job_id, payload=JobUpdate(state=JobState.succeeded, result=result))

    def fail(self, job_id: int, error: str) -> JobResponse:
        return self.report(job_id=job_id, payload=JobUpdate(state=JobState.failed, error=error))


class Workers(Resource, ActionMixin):
    """Workers — `/workers`."""

    path = "/workers"

    def __init__(self, rest: RestClient):
        super().__init__(rest)
        self.jobs = Jobs(rest)

    @action("POST", "connect")
    def connect(self, payload: WorkerConnectRequest) -> WorkerConnection:
        """The broker and queues for a worker that runs the given job types."""

    @action("GET", "job_types")
    def job_types(self) -> list[JobTypeInfo]:
        """Every job type the backend creates, and the queue that carries it."""
