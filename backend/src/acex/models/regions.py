from sqlmodel import SQLModel, Field
from typing import Optional

from acex_devkit.models.region import (
    RegionBase as RegionSchema,
    RegionSiteInfo,
    RegionResponse,
)


class RegionBase(RegionSchema, SQLModel):
    pass


class Region(RegionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class SiteRegionAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    region_name: str
    site_name: str


class SiteRegionAssignmentCreate(SQLModel):
    region_name: str
    site_name: str
