from dataclasses import dataclass

from acex.messaging import queue_for
from acex_devkit.models.job import JobSubjectType
from pydantic import BaseModel


@dataclass(frozen=True)
class JobType:
    """What a job type takes and gives back. Workers hold the code that runs it."""

    #: Also the Celery task name and what the queue is routed by, e.g. "acex.ztp.discover".
    name: str
    #: The job's data. Ids only: workers fetch everything else from the API.
    data: type[BaseModel]
    #: What a worker reports back, or None for jobs whose effect is the point.
    result: type[BaseModel] | None = None
    #: The subject type and the field of `data` holding its id.
    subject: tuple[JobSubjectType, str] | None = None
    max_attempts: int = 3


class UnknownJobType(LookupError):
    pass


class JobTypeRegistry:
    def __init__(self):
        self._types: dict[str, JobType] = {}

    def register(self, job_type: JobType) -> JobType:
        if job_type.name in self._types:
            raise ValueError(f"Job type {job_type.name!r} is already registered.")
        # Refuse a job type no queue would carry before any job of it is made.
        queue_for(job_type.name)
        if job_type.subject is not None and job_type.subject[1] not in job_type.data.model_fields:
            raise ValueError(
                f"Job type {job_type.name!r} takes its subject from {job_type.subject[1]!r}, "
                f"which {job_type.data.__name__} has no field for."
            )
        self._types[job_type.name] = job_type
        return job_type

    def get(self, name: str) -> JobType:
        try:
            return self._types[name]
        except KeyError:
            raise UnknownJobType(f"Unknown job type {name!r}; known: {', '.join(sorted(self._types))}.") from None

    def __iter__(self):
        return iter(sorted(self._types.values(), key=lambda job_type: job_type.name))


#: The job types the backend can create.
registry = JobTypeRegistry()
