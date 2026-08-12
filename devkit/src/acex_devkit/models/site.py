from pydantic import BaseModel, Field

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.contact import ContactResponse


class SiteBase(BaseModel):
    name: str = Field(default="")
    display_name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None


class SiteCreate(SiteBase):
    pass


class SiteUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None


class SiteResponse(PersistedResponse, SiteBase):
    contacts: list[ContactResponse] = []
