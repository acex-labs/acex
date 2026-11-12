from datetime import datetime

from sqlmodel import Field, SQLModel


class EnabledHardwareModelRow(SQLModel, table=True):
    """A declared hardware model the installation runs. No row: not enabled."""

    __tablename__ = "enabled_hardware_model"

    hardware_model: str = Field(primary_key=True)
    #: Who enabled it, or what: the inventory or a ZTP review when an asset of the model entered it.
    enabled_by: str | None = None
    enabled_at: datetime | None = None


__all__ = ["EnabledHardwareModelRow"]
