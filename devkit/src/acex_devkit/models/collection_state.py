from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

MESSAGE_LENGTH = 500


class CollectionFailure(StrEnum):
    unreachable = "unreachable"
    authentication_failed = "authentication_failed"
    privilege_failed = "privilege_failed"
    ssh_algorithm = "ssh_algorithm"
    driver_unavailable = "driver_unavailable"
    no_management_ip = "no_management_ip"
    no_credentials = "no_credentials"
    empty_configuration = "empty_configuration"
    other = "other"


class CollectionStatus(StrEnum):
    ok = "ok"
    failing = "failing"


class CollectionResult(BaseModel):
    """What a collection agent found when it last tried a node. A failure without a category is `other`."""

    node_id: int
    ok: bool
    category: CollectionFailure | None = None
    message: str | None = Field(default=None, max_length=MESSAGE_LENGTH)


class CollectionResultsUpload(BaseModel):
    results: list[CollectionResult]


class CollectionResultsAccepted(BaseModel):
    accepted: int
    unknown_nodes: list[int] = []


class NodeCollectionStateResponse(BaseModel):
    status: CollectionStatus
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    failing_since: datetime | None = None
    consecutive_failures: int = 0
    category: CollectionFailure | None = None
    message: str | None = None
    agent_id: int | None = None
    agent_name: str | None = None
