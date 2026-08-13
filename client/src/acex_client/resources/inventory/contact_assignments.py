from acex_devkit.models.assignment import (
    ContactAssignmentCreate,
    ContactAssignmentResponse,
)

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    ListMixin,
    Resource,
)


class ContactAssignments(Resource, ListMixin, CreateMixin, DeleteMixin):
    path = "/inventory/contact_assignments"
    response_model = ContactAssignmentResponse
    list_model = ContactAssignmentResponse
    create_model = ContactAssignmentCreate
