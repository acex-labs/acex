"""Provider failures, independent of the SDK or protocol that produced them."""

from typing import Literal

ErrorKind = Literal["transient", "rate_limit", "auth", "invalid_request", "unsupported"]


class ProviderError(Exception):
    """A request to a model failed.

    kind decides what happens next:
      transient, rate_limit  try the next level of the chain
      unsupported            the model refused a feature of the request (tools,
                             a reasoning setting); retry the same level without it
      auth, invalid_request  configuration problem; fail
    """

    def __init__(self, message: str, kind: ErrorKind, status: int | None = None, param: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.param = param

    @property
    def failover(self) -> bool:
        return self.kind in ("transient", "rate_limit")


class AllLevelsExhaustedError(Exception):
    """Raised when every level in a failover chain failed."""

    def __init__(self, task: str, failures: list[tuple[str, str]]):
        self.task = task
        self.failures = failures
        detail = "; ".join(f"{label}: {error}" for label, error in failures)
        super().__init__(f"All {len(failures)} level(s) failed for task '{task}': {detail}")
