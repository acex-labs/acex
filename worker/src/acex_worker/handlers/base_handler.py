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
    gives no result, and raises when the job cannot be done. The job's error is
    the exception's message, which is what the user reads: a ValueError or a
    RuntimeError says it all, any other is prefixed with its type, e.g.
    "KeyError: 'x'". Which handler raised it and where is in the log.
    """

    EXPLAINED = (ValueError, RuntimeError, OSError)

    def handle_hook(self, client: Acex, job: JobResponse) -> HandlerResponse:
        try:
            handler_result = self.handle(client, job)
        except Exception as exc:
            log.exception(f"Handler {self.__class__.__name__} for job {job.id} ({job.type}) raised '{exc}'")
            explained = isinstance(exc, self.EXPLAINED) and str(exc)
            error = str(exc) if explained else f"{type(exc).__name__}: {exc}"
            return HandlerResponse(job_id=job.id, success=False, error=error)

        # The backend checks the result against the job type, and refuses one
        # that is missing for a job type that needs it.
        result = handler_result.model_dump(mode="json") if handler_result is not None else None
        return HandlerResponse(job_id=job.id, success=True, result=result)

    @abstractmethod
    def handle(self, client: Acex, job: JobResponse) -> BaseModel | None: ...
