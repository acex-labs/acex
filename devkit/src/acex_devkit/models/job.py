from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class JobState(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class JobSubjectType(StrEnum):
    """The kind of object a job is about, for finding every job that concerns it."""

    node = "node"
    logical_node = "logical_node"
    asset = "asset"


class JobBase(BaseModel):
    #: The job type, e.g. "acex.ztp.discover". Also the Celery task name.
    type: str
    #: Set on the jobs of a batch. Only one level: a child has no children.
    parent_id: int | None = None
    #: Derived from the job type and its data, never set by the caller.
    subject_type: JobSubjectType | None = None
    subject_id: int | None = None
    #: Typed per job type, and only ids: workers fetch the rest from the API.
    data: dict | None = None
    #: Typed per job type; set when a worker reports success.
    result: dict | None = None
    state: JobState = JobState.queued
    attempts: int = 0
    error: str | None = None
    #: The user's `sub`, or "system" for jobs the backend creates itself.
    created_by: str
    claimed_by: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobResponse(PersistedResponse, JobBase):
    #: On a batch's parent: how many of its jobs are in each state. The
    #: parent's own state is derived from these.
    children: dict[JobState, int] | None = None
