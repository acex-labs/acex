from pydantic import BaseModel, Field
from typing import Optional

from acex_devkit.models.base import PersistedResponse


class ContactBase(BaseModel):
    name: str = Field(default="")
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None


class ContactResponse(PersistedResponse, ContactBase):
    pass
