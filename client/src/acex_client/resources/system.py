from acex_devkit.models.auth_config import AuthConfig
from acex_devkit.models.compliance import ComplianceResult, SiteComplianceResult

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)


class SystemNamespace(Resource, ActionMixin):
    """System endpoints — `/auth/config` and `/health/*` aliases for compliance.

    The backend's `/health/node_instance/{id}` and `/health/site/{name}` are
    documented as aliases of `/operations/compliance/{id}` and
    `/operations/compliance/site/{name}` respectively; this namespace exposes
    them under `client.system.*` for callers that prefer the health framing.
    """

    path = ""
    response_model = None  # type: ignore
    list_model = None  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "/auth/config")
    def auth_config(self) -> AuthConfig: ...

    @action("GET", "/health/node_instance/{node_instance_id}")
    def health_node(self, node_instance_id: int) -> ComplianceResult: ...

    @action("GET", "/health/site/{site_name}")
    def health_site(self, site_name: str) -> SiteComplianceResult: ...
