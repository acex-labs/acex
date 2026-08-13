from acex_devkit.models.compliance import ComplianceResult, SiteComplianceResult

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class Compliance(Resource, ActionMixin):
    """Compliance checks — `/operations/compliance/*`.

    Returns diff summaries (no added/removed/changed lists) per node or
    aggregated per site. The health endpoints `/health/*` are aliases of
    these and are exposed via `client.system.health_*` instead.
    """

    path = "/operations/compliance"
    response_model = ComplianceResult  # type: ignore
    list_model = ComplianceResult  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "{node_instance_id}")
    def check(self, node_instance_id: int) -> ComplianceResult: ...

    @action("GET", "site/{site_name}")
    def site(self, site_name: str) -> SiteComplianceResult: ...
