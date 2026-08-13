from typing import Any

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class Grafana(Resource, ActionMixin):
    """Grafana dashboards and datasources — read-only operational endpoints.

    Mounted under `/observability/grafana/`. Exposed as
    `client.observability.grafana` rather than as separate top-level resources
    because they're read-only renders, not CRUD domains.
    """

    path = "/observability/grafana"
    response_model = Any  # type: ignore
    list_model = Any  # type: ignore
    create_model = Any  # type: ignore
    update_model = Any  # type: ignore

    @action("GET", "dashboards")
    def dashboards(self) -> list[dict]: ...

    @action("GET", "dashboards/{uid}")
    def dashboard(self, uid: str) -> dict: ...

    @action("GET", "datasources")
    def datasources(self) -> list[dict]: ...

    @action("GET", "datasources/{uid}")
    def datasource(self, uid: str) -> dict: ...
