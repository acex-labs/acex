from acex_devkit.models.lldp_neighbor import LldpNeighborResponse, LldpNeighborUpload
from acex_devkit.models.lldp_topology import (
    LldpTopology,
    LldpUploadResult,
)

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class Lldp(Resource, ActionMixin):
    """LLDP neighbors — `/operations/lldp_neighbors/*`."""

    path = "/operations/lldp_neighbors"
    response_model = LldpNeighborResponse  # type: ignore
    list_model = LldpNeighborResponse  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("POST", "")
    def upload(self, payload: LldpNeighborUpload) -> LldpUploadResult: ...

    @action("GET", "topology")
    def topology(
        self,
        site: str | None = None,
        node_id: int | None = None,
        hops: int = 1,
    ) -> LldpTopology: ...

    @action("GET", "by-site/{site}")
    def by_site(self, site: str) -> list[LldpNeighborResponse]: ...

    @action("GET", "{node_instance_id}")
    def get(self, node_instance_id: int) -> list[LldpNeighborResponse]: ...

    @action("GET", "{node_instance_id}/reverse")
    def reverse(self, node_instance_id: int) -> list[LldpNeighborResponse]: ...
