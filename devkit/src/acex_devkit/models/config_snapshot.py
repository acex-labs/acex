from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.composed_configuration import ComposedConfiguration


class ConfigOutput(StrEnum):
    PARSED = "parsed"
    RENDERED = "rendered"


class DeviceConfigUpload(BaseModel):
    content: str


class ConfigSnapshotListItem(BaseModel):
    id: int
    hash: str
    created_at: datetime
    node_instance_id: str


class ConfigSnapshotDetail(BaseModel):
    """Latest or specific observed config for a node instance.

    Returned by `GET .../observed/latest` and `GET .../observed/{config_id}`.
    Note: backend base64-encodes string content before returning; the client
    decodes before constructing this model.
    """

    node_instance_id: str
    content: str | ComposedConfiguration
    hash: str
    created_at: datetime


class ConfigDiffSide(BaseModel):
    hash: str
    created_at: datetime | None = None


class ConfigDiffEntry(BaseModel):
    """One row in a unified diff between two observed configs."""

    type: str  # "equal" | "add" | "remove"
    line_a: int | None = None
    line_b: int | None = None
    text: str


class ConfigDiffStats(BaseModel):
    added: int = 0
    removed: int = 0
    equal: int = 0


class ConfigDiffResult(BaseModel):
    """Result of `GET .../observed/diff?a=&b=`."""

    config_a: ConfigDiffSide
    config_b: ConfigDiffSide
    diff: list[ConfigDiffEntry] = []
    stats: ConfigDiffStats = ConfigDiffStats()


class ConfigChangeListItem(BaseModel):
    """One row in `GET /operations/configuration/changes`."""

    id: int
    node_instance_id: str
    hostname: str | None = None
    site: str | None = None
    role: str | None = None
    hash: str
    created_at: datetime
    previous_hash: str | None = None
    previous_created_at: datetime | None = None


class ConfigChangeListResult(BaseModel):
    """Paginated list of config changes."""

    items: list[ConfigChangeListItem] = []
    total: int = 0
    limit: int = 100
    offset: int = 0
