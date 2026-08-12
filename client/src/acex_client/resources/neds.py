from acex_devkit.models.ned import Ned

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class Neds(Resource, ActionMixin):
    """NED (Network Element Driver) metadata and downloads — `/neds/*`."""

    path = "/neds"
    response_model = Ned  # type: ignore
    list_model = Ned  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "")
    def list(self) -> list[Ned]: ...

    @action("GET", "{ned_id}")
    def get(self, ned_id: str) -> Ned: ...

    @action("GET", "download/{filename}")
    def download(self, filename: str) -> bytes: ...
