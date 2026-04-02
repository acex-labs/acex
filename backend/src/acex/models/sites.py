from sqlmodel import SQLModel, Field
from typing import Optional

from acex.models.contacts import ContactResponse


class SiteBase(SQLModel):
    name: str = Field(default="")
    display_name: Optional[str] = Field(default=None)
    address: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    description: Optional[str] = Field(default=None)


class Site(SiteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class SiteResponse(SiteBase):
    id: Optional[int] = Field(default=None)
    contacts: list[ContactResponse] = Field(default_factory=list)
