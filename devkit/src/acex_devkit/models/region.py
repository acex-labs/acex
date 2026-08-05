from pydantic import BaseModel, Field

from acex_devkit.models.base import PersistedResponse


class RegionBase(BaseModel):
    name: str = Field(default="")
    display_name: str | None = None
    description: str | None = None


class RegionSiteInfo(BaseModel):
    name: str
    display_name: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class RegionResponse(PersistedResponse, RegionBase):
    sites: list[RegionSiteInfo] = []
