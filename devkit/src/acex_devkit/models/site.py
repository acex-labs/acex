from pydantic import BaseModel, Field
from typing import Optional

from acex_devkit.models.base import PersistedResponse
from acex_devkit.models.contact import ContactResponse


class SiteBase(BaseModel):
    name: str = Field(default="")
    display_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None


class SiteResponse(PersistedResponse, SiteBase):
    contacts: list[ContactResponse] = []
