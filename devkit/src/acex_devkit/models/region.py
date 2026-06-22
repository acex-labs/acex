from pydantic import BaseModel, Field
from typing import Optional

from acex_devkit.models.base import PersistedResponse


class RegionBase(BaseModel):
    name: str = Field(default="")
    display_name: Optional[str] = None
    description: Optional[str] = None


class RegionSiteInfo(BaseModel):
    name: str
    display_name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RegionResponse(PersistedResponse, RegionBase):
    sites: list[RegionSiteInfo] = []
