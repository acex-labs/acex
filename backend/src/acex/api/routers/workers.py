from acex.api import auth as _auth
from acex.constants import BASE_URL
from acex.jobs import InvalidJobResult, JobConflict, JobNotFound
from acex_devkit.models.job import JobResponse, JobState, JobSubjectType, JobSummary, JobUpdate
from acex_devkit.models.pagination import PaginatedResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError


def _worker(user: dict) -> str:
    """Who is reporting: the client id of a worker's service account, else the user."""
    return user.get("azp") or user.get("sub") or "anonymous"


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/workers", tags=["Workers"])
    jobs = automation_engine.jobs

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
        and skips the job.
        """
        try:
            return jobs.update(job_id, report, worker=_worker(user))
        except JobNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except JobConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"reason": str(exc), "job": exc.job.model_dump(mode="json")},
            ) from exc
        except InvalidJobResult as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(include_url=False, include_context=False),
            ) from exc

    return router
