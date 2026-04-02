from sqlmodel import SQLModel, Field
from typing import Optional


class ContactBase(SQLModel):
    name: str = Field(default="")
    display_name: Optional[str] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    family_name: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)


class Contact(ContactBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class ContactResponse(ContactBase):
    id: Optional[int] = Field(default=None)


class ContactAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    contact_name: str
    site_name: str


class ContactAssignmentCreate(SQLModel):
    contact_name: str
    site_name: str
