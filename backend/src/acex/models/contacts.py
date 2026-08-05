from acex_devkit.models.contact import ContactBase as ContactSchema
from acex_devkit.models.contact import ContactResponse
from sqlmodel import Field, SQLModel


class ContactBase(ContactSchema, SQLModel):
    pass


class Contact(ContactBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class ContactAssignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    contact_name: str
    site_name: str


class ContactAssignmentCreate(SQLModel):
    contact_name: str
    site_name: str


__all__ = ["ContactBase", "Contact", "ContactAssignment", "ContactAssignmentCreate", "ContactResponse"]
