import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime

from acex.compliance.configuration import ConfigurationCheck
from acex.compliance.software import SoftwareCheck
from acex.config_diff import DiffLogicalNode
from acex_devkit.models.compliance import (
    ComplianceOverview,
    ComplianceSummary,
    ConfigurationCompliance,
    ConfigurationStatus,
    NodeCompliance,
    SiteCompliance,
    SoftwareCompliance,
)
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.policy import SoftwarePolicyResponse
from fastapi import HTTPException, Response

log = logging.getLogger(__name__)


class ComplianceService:
    """Compliance of nodes, summed up per site, per region and over the whole installation.

    A site or a region is measured when asked: every node in scope is checked on each call. The whole installation is
    measured in the background, at start and then every `refresh_seconds`, and `latest_overview` answers from the last
    measurement, since measuring every node takes minutes.
    """

    #: How often the overview of the installation is measured again.
    refresh_seconds = 600
    #: How long the first answer after a start waits for the first measurement before it gives up.
    first_answer_seconds = 20

    def __init__(self, inventory, device_config_manager, software_policies):
        self._overview: ComplianceOverview | None = None
        self._measured_at: datetime | None = None
        self._task: asyncio.Task | None = None
        self.inventory = inventory
        self.configuration = ConfigurationCheck(DiffLogicalNode(inventory, device_config_manager))
        self.software = SoftwareCheck(software_policies)

    async def node(self, node_instance_id: str) -> NodeCompliance:
        return await self.measure(node_instance_id, self.software.approved())

    async def site(self, site_name: str) -> SiteCompliance:
        sites = await self.inventory.sites.query(name=site_name, limit=None)
        if not any(s.name == site_name for s in sites.items):
            raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")
        results = await self.measure_all(await self.nodes(sites=[site_name]))
        return SiteCompliance(summary=self.summarize(list(results.values())), nodes=results)

    async def region(self, region_name: str) -> ComplianceOverview:
        regions = await self.inventory.regions.query(name=region_name, limit=None)
        if not any(r.name == region_name for r in regions.items):
            raise HTTPException(status_code=404, detail=f"Region '{region_name}' not found")
        # Assignments are looked up by a name pattern; only this region's count.
        assignments = self.inventory.region_assignment_manager.list_assignments(region_name=region_name)
        site_names = sorted({a.site_name for a in assignments if a.region_name == region_name})
        nodes = await self.nodes(sites=site_names) if site_names else []
        return self.overview_of(nodes, await self.measure_all(nodes))

    def start(self) -> None:
        """Starts measuring the installation in the background, once."""
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._keep_measured())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    async def _keep_measured(self) -> None:
        while True:
            try:
                self._overview = await self.overview()
                self._measured_at = datetime.now(UTC)
            except Exception:
                log.exception("Could not measure the compliance of the installation")
            await asyncio.sleep(self.refresh_seconds)

    async def latest_overview(self, response: Response) -> ComplianceOverview:
        """The overview of the installation as last measured, at once; `X-Measured-At` says when."""
        self.start()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.first_answer_seconds
        while self._overview is None and loop.time() < deadline:
            await asyncio.sleep(0.25)
        if self._overview is None:
            raise HTTPException(
                status_code=503,
                detail="The installation is being measured for the first time; try again in a minute.",
                headers={"Retry-After": "30"},
            )
        response.headers["X-Measured-At"] = self._measured_at.isoformat()
        return self._overview

    async def overview(self) -> ComplianceOverview:
        """Every node, with a summary per site and per region besides the total."""
        nodes = await self.nodes()
        results = await self.measure_all(nodes)
        overview = self.overview_of(nodes, results)
        sites_of = defaultdict(set)
        for assignment in self.inventory.region_assignment_manager.list_assignments():
            sites_of[assignment.region_name].add(assignment.site_name)
        overview.regions = {
            region: self.summarize([results[n.id] for n in nodes if n.site in sites])
            for region, sites in sorted(sites_of.items())
        }
        return overview

    def overview_of(self, nodes: list[NodeListItem], results: dict[int, NodeCompliance]) -> ComplianceOverview:
        """A summary per site and over all of `nodes`; a node without a site counts in the total only."""
        by_site = defaultdict(list)
        for node in nodes:
            if node.site:
                by_site[node.site].append(results[node.id])
        return ComplianceOverview(
            summary=self.summarize(list(results.values())),
            sites={site: self.summarize(site_results) for site, site_results in sorted(by_site.items())},
        )

    async def measure_all(self, nodes: list[NodeListItem]) -> dict[int, NodeCompliance]:
        """Every node measured against the software policy as it stands now, read once. A node that cannot be
        measured, such as one whose asset is gone, is left unmeasured and does not fail the others."""
        approved = self.software.approved()
        results = {}
        for node in nodes:
            # Measuring a node is plain blocking work; this lets the server answer other requests in between.
            await asyncio.sleep(0)
            try:
                results[node.id] = await self.measure(str(node.id), approved)
            except Exception:
                log.exception("Could not measure the compliance of node %s", node.id)
                results[node.id] = NodeCompliance(
                    configuration=ConfigurationCompliance(status=ConfigurationStatus.not_collected),
                    software=SoftwareCompliance(),
                )
        return results

    async def measure(self, node_instance_id: str, approved: list[SoftwarePolicyResponse]) -> NodeCompliance:
        node = await self.inventory.node_instances.get(node_instance_id)  # 404 for an unknown node
        return NodeCompliance(
            configuration=await self.configuration.node(node_instance_id),
            software=self.software.node(node, approved),
        )

    async def nodes(self, sites: list[str] | None = None) -> list[NodeListItem]:
        """Every node, or every node at one of `sites` by exact name."""
        return (await self.inventory.node_instances.query(site=sites, limit=None)).items

    def summarize(self, results: list[NodeCompliance]) -> ComplianceSummary:
        return ComplianceSummary(
            configuration=self.configuration.summarize([r.configuration for r in results]),
            software=self.software.summarize([r.software for r in results]),
        )
