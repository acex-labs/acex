from acex_devkit.models.site import SiteBase as SiteSchema
from acex_devkit.models.site import SiteResponse
from sqlmodel import Field, SQLModel


class SiteBase(SiteSchema, SQLModel):
    pass


class Site(SiteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


__all__ = ["SiteBase", "Site", "SiteResponse"]
