from datetime import datetime

from sqlmodel import Field, SQLModel


class SoftwarePolicyRow(SQLModel, table=True):
    """A software version approved for a vendor's devices, or for one hardware model of it."""

    __tablename__ = "software_policy"

    id: int | None = Field(default=None, primary_key=True)
    #: A `Vendor` value.
    vendor: str = Field(index=True)
    #: None for every model of the vendor.
    hardware_model: str | None = None
    #: An `OS` value.
    os: str
    os_version: str
    #: At most one per vendor and hardware model, None included: checked on save, since a unique
    #: constraint lets NULLs repeat.
    golden: bool = False
    updated_by: str | None = None
    updated_at: datetime | None = None


__all__ = ["SoftwarePolicyRow"]
