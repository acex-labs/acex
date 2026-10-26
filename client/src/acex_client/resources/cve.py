"""CVE client resources — interact with CVE-related endpoints."""

from __future__ import annotations

from acex_client.http import RestClient
from acex_client.resources.base import ActionMixin, Resource, action
from acex_devkit.models.cve import CveApiKeyUpdate, CveCreate, CveDiscoverData, CveResponse
from acex_devkit.models.job import JobResponse


class CveApiKey(Resource, ActionMixin):
    """The backend's singleton NVD API key — `/cves/api_key`."""

    path = "/cves/api_key"

    @action("GET", "")
    def get(self) -> str | None:
        """Get the backend's NVD API key, or None if none is configured."""

    @action("PUT", "")
    def update(self, payload: CveApiKeyUpdate) -> None:
        """Store or replace the backend's encrypted NVD API key."""

    @action("DELETE", "")
    def delete(self) -> None:
        """Remove the backend's NVD API key."""


class Cves(Resource, ActionMixin):
    """CVE resources — `/cves`."""

    path = "/cves"

    def __init__(self, rest: RestClient):
        super().__init__(rest)
        self.api_key = CveApiKey(rest)

    @action("POST", "discover")
    def discover(self, payload: CveDiscoverData) -> JobResponse:
        """Queue a CVE discovery job."""

    @action("GET", "{cve_id}")
    def get(self, cve_id: int) -> CveResponse: ...

    @action("POST", "")
    def create(self, payload: CveCreate) -> CveResponse:
        """Create a CVE from NVD data."""

    @action("POST", "bulk")
    def bulk_create(self, payload: list[CveCreate]) -> list[CveResponse]:
        """Create or refresh CVEs in one request."""

    @action("PATCH", "{cve_id}")
    def update(self, cve_id: int, payload: CveCreate) -> CveResponse:
        """Update a CVE's NVD data."""
