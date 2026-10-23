"""CVE client resources — interact with CVE-related endpoints."""

from __future__ import annotations

from acex_devkit.models.cve import CveCreate, CveResponse
from acex_client.resources.base import ActionMixin, Resource, action
class Cves(Resource, ActionMixin):
    """CVE resources — `/cves`."""

    path = "/cves"

    @action("GET", "{cve_id}")
    def get(self, cve_id: int) -> CveResponse: ...


    @action("POST", "")
    def create(self, payload: CveCreate) -> CveResponse:
        """Create a CVE from NVD data."""

    @action("PATCH", "{cve_id}")
    def update(self, cve_id: int, payload: CveCreate) -> CveResponse:
        """Update a CVE's NVD data."""