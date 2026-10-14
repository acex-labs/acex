from datetime import datetime

from sqlmodel import Field, SQLModel


class ZtpVendorClassRow(SQLModel, table=True):
    """A DHCP vendor class (option 60) and the ZTP method devices sending it bootstrap with."""

    __tablename__ = "ztp_vendor_class"

    id: int | None = Field(default=None, primary_key=True)
    vendor_class: str = Field(unique=True)
    #: A `ZtpVendorClassMatch` value.
    match: str = "exact"
    #: A `ZtpMethod` value, a plain string like `ztp_method.method`. None until mapped.
    method: str | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None


__all__ = ["ZtpVendorClassRow"]
