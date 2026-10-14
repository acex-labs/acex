import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from acex_client import Acex
from acex_devkit.models.job import JobResponse
from pydantic import BaseModel

log = logging.getLogger("acex_worker")


@dataclass
class HandlerResponse:
    """How a handler run ended, for execute() to report."""

    job_id: int
    success: bool
    result: dict | None = None
    error: str | None = None


class Handler(ABC):
    """
    Base class for handlers.

    A handler returns its job type's result model, or None for a job type that
    gives no result, and raises when the job cannot be done.
    """

    def handle_hook(self, client: Acex, job: JobResponse) -> HandlerResponse:
        try:
            handler_result = self.handle(client, job)
        except Exception as exc:
            exc_str = f"Handler {self.__class__.__name__} for job {job.id} ({job.type}) raised '{exc}'"
            log.exception(exc_str)
            return HandlerResponse(job_id=job.id, success=False, error=exc_str)

        # The backend checks the result against the job type, and refuses one
        # that is missing for a job type that needs it.
        result = handler_result.model_dump(mode="json") if handler_result is not None else None
        return HandlerResponse(job_id=job.id, success=True, result=result)

    @abstractmethod
    def handle(self, client: Acex, job: JobResponse) -> BaseModel | None: ...
