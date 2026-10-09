import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from acex_client import Acex
from acex_devkit.models.job import JobResponse

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
    Base class for handlers
    """

    def handle_hook(self, client: Acex, job: JobResponse) -> HandlerResponse:
        try:
            handler_result = self.handle(client, job)
        except Exception as exc:
            exc_str = f"Handler {self.__class__.__name__}for job {job.id} ({job.type}) raised '{exc}'"
            log.exception(exc_str)
            return HandlerResponse(job_id=job.id, success=False, error=exc_str)

        if handler_result is None:
            return HandlerResponse(
                job_id=job.id, success=False, error=f"Handler {self.__class__.__name__} returned None"
            )

        return HandlerResponse(job_id=job.id, success=True, result=handler_result)

    @abstractmethod
    def handle(self, client: Acex, job: JobResponse) -> dict: ...
