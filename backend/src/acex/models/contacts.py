from sqlmodel import SQLModel, Field
from typing import Optional

from acex_devkit.models.contact import ContactBase as ContactSchema, ContactResponse


class ContactBase(ContactSchema, SQLModel):
    pass


class Contact(ContactBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class ContactAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    contact_name: str
    site_name: str


class ContactAssignmentCreate(SQLModel):
    contact_name: str
    site_name: str
