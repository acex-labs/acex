from datetime import datetime

from sqlmodel import Field, SQLModel


class ZtpMethodRow(SQLModel, table=True):
    """What an administrator has chosen for one ZTP method.

    The methods themselves are code (`ZtpMethod`); a row only holds choices,
    and there is one for every method.
    """

    __tablename__ = "ztp_method"

    # A plain string rather than a database enum, so a new method needs no migration.
    method: str = Field(primary_key=True)
    #: The NED discovery uses. Not a foreign key: NEDs are installed packages, not rows.
    ned: str | None = None
    #: The temporary login the bootstrap gives a device, for discovery to log in
    #: with until onboarding rotates it. Served to anyone who fetches the
    #: bootstrap, so stored and shown in the clear.
    bootstrap_username: str | None = None
    bootstrap_password: str | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None


__all__ = ["ZtpMethodRow"]
