from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, ConfigDict
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc)

# SQL related stuff
class CveModel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cve_id: str = Field(unique=True, index=True)
    published: datetime | None = Field(default=None, index=True)
    last_modified: datetime | None = Field(default=None, index=True)
    description: str | None = Field(default=None)
    cvss_score: float | None = Field(default=None)
    raw: dict = Field(sa_column=Column(JSONB, nullable=False)) # RAW CVE data from NVD in json format
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime | None = Field(default=None)

# User workflow state for CVEs
class CveState(SQLModel, table=True):
    """User workflow state, kept apart so re-syncing a CVE never overwrites it."""

    cve_id: str = Field(primary_key=True, foreign_key="cvemodel.cve_id")
    status: str = Field(default="new")  # new, acked, mitigated, not_affected
    updated_at: datetime = Field(default_factory=utcnow)

# Sync state for each vendor:part combination
class SyncState(SQLModel, table=True):
    key: str = Field(primary_key=True)  # "<vendor>:<part>"
    last_sync: datetime

class CveDiscoverData(SQLModel):
    vendor: str | None = Field(default="Cisco")
    #start: datetime
    #end: datetime
    
class CveCreate(BaseModel):
    """NVD data sent for ingestion; database IDs and timestamps are server-managed."""

    cve_id: str
    published: datetime | None = None
    last_modified: datetime | None = None
    description: str | None = None
    cvss_score: float | None = None
    raw: dict


class CveResponse(CveCreate):
    """A stored CVE, including its database ID and ingestion timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None