"""Compliance — `/compliance/*`: per node, per site, per region and over the whole installation."""

from __future__ import annotations

from acex_devkit.models.compliance import ComplianceOverview, NodeCompliance, SiteCompliance

from acex_client.resources.base import ActionMixin, Resource, action


class Compliance(Resource, ActionMixin):
    """Compliance — `/compliance`.

    A node and a site come in full; a region and the installation as a summary per site and in total.
    """

    path = "/compliance"

    @action("GET", "")
    def overview(self) -> ComplianceOverview: ...

    @action("GET", "nodes/{node_instance_id}")
    def node(self, node_instance_id: int) -> NodeCompliance: ...

    @action("GET", "sites/{site_name}")
    def site(self, site_name: str) -> SiteCompliance: ...

    @action("GET", "regions/{region_name}")
    def region(self, region_name: str) -> ComplianceOverview: ...
