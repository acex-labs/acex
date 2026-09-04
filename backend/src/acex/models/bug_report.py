from typing import Literal

from pydantic import BaseModel, Field


class BugReportCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    severity: Literal["low", "medium", "high", "critical"]
    steps: str | None = Field(default=None, max_length=2000)
    page_url: str | None = None


class BugReportResponse(BaseModel):
    title: str
    severity: str
    reporter_id: str
    reporter_email: str | None = None
    dispatched_to: list[str] = []
