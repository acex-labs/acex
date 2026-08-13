from acex_devkit.models.contact import ContactCreate, ContactResponse, ContactUpdate

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    GetMixin,
    ListMixin,
    Resource,
    UpdateMixin,
)


class Contacts(Resource, GetMixin, ListMixin, CreateMixin, UpdateMixin, DeleteMixin):
    path = "/inventory/contacts"
    response_model = ContactResponse
    list_model = ContactResponse
    create_model = ContactCreate
    update_model = ContactUpdate
