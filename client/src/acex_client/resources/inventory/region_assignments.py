from acex_devkit.models.assignment import (
    RegionAssignmentCreate,
    RegionAssignmentResponse,
)

from acex_client.resources.base import (
    CreateMixin,
    DeleteMixin,
    ListMixin,
    Resource,
)


class RegionAssignments(Resource, ListMixin, CreateMixin, DeleteMixin):
    path = "/inventory/region_assignments"
    response_model = RegionAssignmentResponse
    list_model = RegionAssignmentResponse
    create_model = RegionAssignmentCreate
