from datetime import UTC, datetime

from acex_devkit.models.job import JobBase as JobSchema
from acex_devkit.models.job import JobResponse, JobState, JobSubjectType
from sqlalchemy import JSON, Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

_JSON = JSON().with_variant(JSONB(), "postgresql")


class Job(JobSchema, SQLModel, table=True):
    __table_args__ = (Index("ix_job_subject", "subject_type", "subject_id"),)

    id: int | None = Field(default=None, primary_key=True)
    type: str = Field(index=True)
    parent_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("job.id", ondelete="CASCADE"), nullable=True, index=True),
    )
    # A plain string rather than a database enum, so a new subject type needs no migration.
    subject_type: JobSubjectType | None = Field(default=None, sa_column=Column(String, nullable=True))
    subject_id: int | None = None
    data: dict | None = Field(default=None, sa_column=Column(_JSON, nullable=True))
    result: dict | None = Field(default=None, sa_column=Column(_JSON, nullable=True))
    state: JobState = Field(default=JobState.queued, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


__all__ = ["Job", "JobResponse", "JobState", "JobSubjectType"]
