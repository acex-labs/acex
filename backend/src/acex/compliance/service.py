from collections import defaultdict

from acex.compliance.configuration import ConfigurationCheck
from acex.compliance.software import SoftwareCheck
from acex.config_diff import DiffLogicalNode
from acex_devkit.models.compliance import ComplianceOverview, ComplianceSummary, NodeCompliance, SiteCompliance
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.policy import SoftwarePolicyResponse
from fastapi import HTTPException


class ComplianceService:
    """Compliance of nodes, summed up per site, per region and over the whole installation.

    Measured when asked: every node in scope is checked on each call.
    """

    def __init__(self, inventory, device_config_manager, software_policies):
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
        """Every node measured against the software policy as it stands now, read once."""
        approved = self.software.approved()
        return {node.id: await self.measure(str(node.id), approved) for node in nodes}

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
