from sqlmodel import SQLModel, Field
from typing import Optional


class RegionBase(SQLModel):
    name: str = Field(default="")
    display_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class Region(RegionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class RegionSiteInfo(SQLModel):
    name: str
    display_name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RegionResponse(RegionBase):
    id: Optional[int] = Field(default=None)
    sites: list[RegionSiteInfo] = Field(default_factory=list)


class SiteRegionAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    region_name: str
    site_name: str


class SiteRegionAssignmentCreate(SQLModel):
    region_name: str
    site_name: str
