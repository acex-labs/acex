"""Compliance summed up per site, region and over the installation, with the inventory and diff faked."""

import asyncio
from types import SimpleNamespace

import pytest
from acex.compliance import ComplianceService
from acex_devkit.models.asset import AssetResponse
from acex_devkit.models.compliance import ConfigurationStatus, SoftwareStatus
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.models.policy import SoftwarePolicyResponse
from fastapi import HTTPException

# node id → (site, desired, compliant); None for a node with no observed configuration
NODES = {
    1: ("sto", 10, 10),
    2: ("sto", 30, 15),
    3: ("got", 10, 5),
    4: ("got", None),
    5: ("sto-lab", 4, 0),
    6: (None, 0, 0),
}
REGIONS = {"nordics": ["sto", "got"], "nordics-lab": ["sto-lab"]}

# node id → its assets as (vendor, hardware model, os, version); two make a cluster
ASSETS = {
    1: [("cisco", "C9300-24T", "cisco_iosxe", "17.9.4a")],  # golden for its model
    2: [("cisco", "C9300-24T", "cisco_iosxe", "17.6.5"), ("cisco", "c9300-24t", "cisco_iosxe", "17.3.1")],
    3: [("juniper", "EX2300-24T", "juniper_junos", "22.4R1")],  # no policy for juniper
    4: [("cisco", "C9300-48P", "cisco_iosxe", None)],  # the vendor's policy, but no version reported
    5: [("cisco", "C9300-48P", "cisco_iosxe", "17.12.3a")],  # golden for the vendor
    6: [("cisco", "C9300-24T", "cisco_iosxe", "17.12.3a")],  # the vendor's golden, but its model has its own
}
APPROVED = [
    ("C9300-24T", "17.9.4a", True),
    ("C9300-24T", "17.6.5", False),
    (None, "17.12.3a", True),
]


class FakePolicies:
    def list_policies(self):
        return [
            SoftwarePolicyResponse(
                id=i, vendor="cisco", hardware_model=model, os="cisco_iosxe", os_version=version, golden=golden
            )
            for i, (model, version, golden) in enumerate(APPROVED)
        ]


def asset(id, vendor, hardware_model, os, os_version):
    return AssetResponse(
        id=id, vendor=vendor, serial_number=f"SN{id}", hardware_model=hardware_model, os=os, os_version=os_version
    )


class FakeInventory:
    def __init__(self):
        self.node_instances = SimpleNamespace(get=self.get_node, query=self.query_nodes)
        self.sites = SimpleNamespace(query=self.query_sites)
        self.regions = SimpleNamespace(query=self.query_regions)
        self.region_assignment_manager = SimpleNamespace(list_assignments=self.list_assignments)
        self.queries = []

    async def get_node(self, id):
        if int(id) not in NODES:
            raise HTTPException(status_code=404)
        assets = [asset(int(id) * 10 + i, *a) for i, a in enumerate(ASSETS[int(id)])]
        if len(assets) > 1:
            return SimpleNamespace(asset=SimpleNamespace(type="asset_cluster", assets=assets))
        return SimpleNamespace(asset=assets[0])

    async def query_nodes(self, site=None, limit=100):
        self.queries.append((site, limit))
        items = [
            NodeListItem(id=i, asset_ref_id=i, logical_node_id=i, site=n[0])
            for i, n in NODES.items()
            if site is None or n[0] in site
        ]
        return SimpleNamespace(items=items)

    async def query_sites(self, name, limit=100):
        names = {n[0] for n in NODES.values() if n[0]}
        return SimpleNamespace(items=[SimpleNamespace(name=s) for s in names if name in s])  # a pattern, like the DB

    async def query_regions(self, name, limit=100):
        return SimpleNamespace(items=[SimpleNamespace(name=r) for r in REGIONS if name in r])

    def list_assignments(self, region_name=""):
        return [
            SimpleNamespace(region_name=r, site_name=s)
            for r, sites in REGIONS.items()
            if region_name in r
            for s in sites
        ]


class FakeDiffer:
    async def observed(self, node_instance_id):
        return None if NODES[int(node_instance_id)][1] is None else object()

    async def diff_against(self, node_instance_id, observed):
        _, desired, compliant = NODES[int(node_instance_id)]
        return SimpleNamespace(
            total_desired=desired,
            total_observed=desired + 1,
            compliant_count=compliant,
            undeclared_count=1,
            unparsed_count=0,
            compliance_percentage=round(compliant / desired * 100, 2) if desired else 100.0,
        )


@pytest.fixture
def service():
    service = ComplianceService(FakeInventory(), device_config_manager=None, software_policies=FakePolicies())
    service.configuration.differ = FakeDiffer()
    return service


def test_a_node_without_observed_configuration_is_not_collected(service):
    result = asyncio.run(service.node("4")).configuration
    assert result.status == ConfigurationStatus.not_collected
    assert result.compliance_percentage is None


def test_an_unknown_node_is_not_found(service):
    with pytest.raises(HTTPException):
        asyncio.run(service.node("99"))


def test_a_site_has_its_nodes_by_exact_name(service):
    result = asyncio.run(service.site("sto"))
    assert set(result.nodes) == {1, 2}
    assert result.summary.configuration.compliance_percentage == 62.5  # 25 of 40, weighted by component


def test_a_site_summary_leaves_out_nodes_not_collected(service):
    summary = asyncio.run(service.site("got")).summary.configuration
    assert (summary.nodes_total, summary.nodes_not_collected) == (2, 1)
    assert summary.compliance_percentage == 50.0


def test_a_region_has_a_summary_per_site_and_in_total(service):
    result = asyncio.run(service.region("nordics"))
    assert list(result.sites) == ["got", "sto"]  # not sto-lab, though its region's name contains "nordics"
    assert result.sites["sto"].configuration.compliant_count == 25
    assert result.summary.configuration.compliance_percentage == 60.0  # 30 of 50
    assert result.summary.configuration.nodes_not_collected == 1


def test_an_unknown_region_is_not_found(service):
    with pytest.raises(HTTPException):
        asyncio.run(service.region("nord"))


def test_the_overview_covers_every_node_without_a_limit(service):
    result = asyncio.run(service.overview())
    assert service.inventory.queries == [(None, None)]
    assert list(result.sites) == ["got", "sto", "sto-lab"]
    assert result.summary.configuration.nodes_total == 6  # the node without a site counts in the total
    assert result.summary.configuration.compliance_percentage == round(30 / 54 * 100, 2)


def test_nothing_desired_is_fully_compliant(service):
    assert asyncio.run(service.node("6")).configuration.compliance_percentage == 100.0


def test_no_measured_node_has_no_percentage(service):
    assert service.summarize([]).configuration.compliance_percentage is None


def statuses(service, node_id):
    return [a.status for a in asyncio.run(service.node(node_id)).software.assets]


def test_an_asset_is_measured_against_its_models_versions(service):
    assert statuses(service, "1") == [SoftwareStatus.golden]
    # Its model approves versions of its own, so the vendor's golden is not allowed on it.
    assert statuses(service, "6") == [SoftwareStatus.not_allowed]


def test_each_asset_of_a_cluster_counts_on_its_own(service):
    software = asyncio.run(service.node("2")).software
    assert [a.status for a in software.assets] == [SoftwareStatus.accepted, SoftwareStatus.not_allowed]
    assert (software.assets_total, software.compliance_percentage) == (2, 50.0)
    assert software.assets[0].golden_version == "17.9.4a"


def test_without_versions_for_its_model_an_asset_falls_back_to_its_vendors(service):
    assert statuses(service, "5") == [SoftwareStatus.golden]
    assert statuses(service, "4") == [SoftwareStatus.unknown_version]


def test_an_asset_no_policy_covers_is_not_measured(service):
    software = asyncio.run(service.node("3")).software
    assert [a.status for a in software.assets] == [SoftwareStatus.no_policy]
    assert software.compliance_percentage is None


def test_a_site_sums_software_over_its_assets(service):
    software = asyncio.run(service.site("sto")).summary.software
    assert (software.golden_count, software.accepted_count, software.not_allowed_count) == (1, 1, 1)
    assert software.compliance_percentage == 66.67


def test_the_overview_has_a_summary_per_region(service):
    result = asyncio.run(service.overview())
    assert list(result.regions) == ["nordics", "nordics-lab"]
    nordics = result.regions["nordics"]
    assert (nordics.configuration.compliance_percentage, nordics.software.compliance_percentage) == (60.0, 66.67)
    assert result.regions["nordics-lab"].software.compliance_percentage == 100.0
    software = result.summary.software
    assert (software.assets_total, software.no_policy_count, software.unknown_version_count) == (7, 1, 1)
    assert software.compliance_percentage == 60.0  # golden 1 and 5, accepted 2a; not allowed 6 and 2b
