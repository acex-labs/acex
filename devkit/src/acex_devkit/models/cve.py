from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer


def utcnow():
    return datetime.now(UTC)


class CveApiKeyUpdate(BaseModel):
    """Replace the backend's NVD API key."""

    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(repr=False)


class CveCreate(BaseModel):
    """NVD data sent for ingestion; database IDs and timestamps are server-managed."""

    cve_id: str
    published: datetime | None = None
    last_modified: datetime | None = None
    description: str | None = None
    cvss_score: float | None = None
    base_severity: str | None = None
    raw: dict

    @field_serializer("published", "last_modified")
    def serialize_date(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None


class CveUpdate(BaseModel):
    """Update fields for an existing CVE."""

    description: str | None = None
    cvss_score: float | None = None
    base_severity: str | None = None
    raw: dict | None = None


class CveResponse(CveCreate):
    """The response model for a CVE, including its database ID and ingestion timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime | None = None


class CveDiscoverResult(BaseModel):
    """The result of a CVE discovery job."""

    model_config = ConfigDict(from_attributes=True)

    vendor: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    discovered_cves: list[str] = Field(default_factory=list)


class CveDiscoverData(BaseModel):
    """The data required to initiate a CVE discovery job."""

    model_config = ConfigDict(from_attributes=True)

    vendor: str | None = "Cisco"
    start: datetime | None = None
    end: datetime | None = None

    @field_serializer("start", "end")
    def serialize_date(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None
