from pydantic import BaseModel

from acex_devkit.models.base import PersistedResponse


class RegionAssignmentCreate(BaseModel):
    region_name: str
    site_name: str


class RegionAssignmentResponse(PersistedResponse):
    region_name: str
    site_name: str


class ContactAssignmentCreate(BaseModel):
    contact_name: str
    site_name: str


class ContactAssignmentResponse(PersistedResponse):
    contact_name: str
    site_name: str
