from acex_devkit.models.region import RegionBase as RegionSchema
from acex_devkit.models.region import RegionResponse, RegionSiteInfo
from sqlmodel import Field, SQLModel


class RegionBase(RegionSchema, SQLModel):
    pass


class Region(RegionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class SiteRegionAssignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    region_name: str
    site_name: str


class SiteRegionAssignmentCreate(SQLModel):
    region_name: str
    site_name: str


__all__ = [
    "RegionBase",
    "Region",
    "SiteRegionAssignment",
    "SiteRegionAssignmentCreate",
    "RegionResponse",
    "RegionSiteInfo",
]
