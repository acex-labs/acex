"""Compliance of nodes, and of the sites, regions and installation they make up.

Compliance has a section per type, the same at every level: a node's result and a summary over many nodes.
Configuration compliance measures the node's configuration against its desired one; software compliance what its
assets run against the software policy.
"""

from enum import StrEnum

from pydantic import BaseModel

from acex_devkit.models.platform import OS


class ConfigurationStatus(StrEnum):
    measured = "measured"
    # No observed configuration parsed into a tree yet: none collected, or no NED that parses it.
    not_collected = "not_collected"


class ConfigurationCompliance(BaseModel):
    """A node's desired configuration against its latest observed one, counted in config components."""

    status: ConfigurationStatus
    total_desired: int = 0
    total_observed: int = 0
    compliant_count: int = 0
    # On the device but not declared: reported, not scored.
    undeclared_count: int = 0
    # Observed lines the NED couldn't parse: how far it covers the device, not whether it complies.
    unparsed_count: int = 0
    # None when not measured. Nothing desired is fully compliant.
    compliance_percentage: float | None = None


class ConfigurationComplianceSummary(BaseModel):
    """Configuration compliance over many nodes. The percentage is over components, so a large node
    weighs more than a small one; nodes not collected count here but are left out of it."""

    nodes_total: int = 0
    nodes_not_collected: int = 0
    total_desired: int = 0
    total_observed: int = 0
    compliant_count: int = 0
    undeclared_count: int = 0
    unparsed_count: int = 0
    # None when no node is measured.
    compliance_percentage: float | None = None


class SoftwareStatus(StrEnum):
    golden = "golden"
    accepted = "accepted"
    # The software policy covers the asset, and does not approve what it runs.
    not_allowed = "not_allowed"
    # No version approved for the asset's model or vendor: nothing to measure against.
    no_policy = "no_policy"
    # Covered by the policy, but the asset hasn't reported its version.
    unknown_version = "unknown_version"


class AssetSoftwareCompliance(BaseModel):
    """What one asset runs against the software policy for its model, or else its vendor."""

    asset_id: int
    hardware_model: str
    os: OS
    os_version: str | None = None
    status: SoftwareStatus
    #: The version to aim for, where the policy names one.
    golden_version: str | None = None


class SoftwareComplianceSummary(BaseModel):
    """Software compliance counted per asset: each asset of a cluster on its own. The percentage is of the assets
    measured, golden and accepted against not allowed; those without a policy or a known version count here but
    are left out of it."""

    assets_total: int = 0
    golden_count: int = 0
    accepted_count: int = 0
    not_allowed_count: int = 0
    no_policy_count: int = 0
    unknown_version_count: int = 0
    # None when no asset is measured.
    compliance_percentage: float | None = None


class SoftwareCompliance(SoftwareComplianceSummary):
    """A node's software compliance, asset by asset."""

    assets: list[AssetSoftwareCompliance] = []


class NodeCompliance(BaseModel):
    configuration: ConfigurationCompliance
    software: SoftwareCompliance


class ComplianceSummary(BaseModel):
    configuration: ConfigurationComplianceSummary = ConfigurationComplianceSummary()
    software: SoftwareComplianceSummary = SoftwareComplianceSummary()


class SiteCompliance(BaseModel):
    """A site's nodes in full, and their summary."""

    summary: ComplianceSummary = ComplianceSummary()
    nodes: dict[int, NodeCompliance] = {}


class ComplianceOverview(BaseModel):
    """A region, or the whole installation: a summary per site and over all of them. For the installation, also
    one per region, where a site in several regions counts in each."""

    summary: ComplianceSummary = ComplianceSummary()
    sites: dict[str, ComplianceSummary] = {}
    regions: dict[str, ComplianceSummary] = {}
