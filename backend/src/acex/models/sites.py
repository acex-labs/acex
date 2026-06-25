from sqlmodel import SQLModel, Field
from typing import Optional

from acex_devkit.models.site import SiteBase as SiteSchema, SiteResponse


class SiteBase(SiteSchema, SQLModel):
    pass


class Site(SiteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
