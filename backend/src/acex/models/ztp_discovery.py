from datetime import UTC, datetime

from acex_devkit.models.ztp import ZtpReviewStatus
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlmodel import Field, SQLModel


class ZtpDiscovery(SQLModel, table=True):
    """Evidence from one ZTP discovery: the device at `source_ip` says it is `serial_number`.

    Discovery never changes assets or nodes; an administrator approves or rejects
    what is recorded here first.
    """

    __tablename__ = "ztp_discovery"

    id: int | None = Field(default=None, primary_key=True)
    #: One discovery per job, so a worker resending its report adds nothing.
    job_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("job.id", ondelete="SET NULL"), nullable=True, unique=True),
    )
    source_ip: str = Field(index=True)
    serial_number: str = Field(index=True)
    vendor: str | None = None
    hardware_model: str | None = None
    os: str | None = None
    os_version: str | None = None
    node_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("node.id", ondelete="SET NULL"), nullable=True, index=True),
    )
    # A plain string rather than a database enum, so a new review status needs no migration.
    review_status: ZtpReviewStatus = Field(
        default=ZtpReviewStatus.unreviewed, sa_column=Column(String, nullable=False, index=True)
    )
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


__all__ = ["ZtpDiscovery"]
