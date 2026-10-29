from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utcnow():
    return datetime.now(UTC)


class CveModelRow(SQLModel, table=True):
    """A CVE entry in the database, storing its metadata and raw NVD data."""

    __tablename__ = "cve"

    id: int | None = Field(default=None, primary_key=True)
    cve_id: str = Field(unique=True, index=True)
    published: datetime | None = Field(default=None, index=True)
    last_modified: datetime | None = Field(default=None, index=True)
    description: str | None = Field(default=None)
    cvss_score: float | None = Field(default=None)
    base_severity: str | None = Field(default=None)
    raw: dict = Field(sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=False))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime | None = Field(default=None)


class CveState(SQLModel, table=True):
    """User workflow state, kept apart so re-syncing a CVE never overwrites it."""

    __tablename__ = "cve_state"

    cve_id: str = Field(primary_key=True, foreign_key="cve.cve_id")
    status: str = Field(default="new")  # new, acked, mitigated, not_affected
    updated_at: datetime = Field(default_factory=utcnow)


class SyncState(SQLModel, table=True):
    __tablename__ = "sync_state"

    key: str = Field(primary_key=True)  # "<vendor>:<part>"
    last_sync: datetime = Field(default_factory=utcnow)
