from pydantic import BaseModel, Field

from acex_devkit.models.base import PersistedResponse


class ContactBase(BaseModel):
    name: str = Field(default="")
    display_name: str | None = None
    first_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None


class ContactResponse(PersistedResponse, ContactBase):
    pass
