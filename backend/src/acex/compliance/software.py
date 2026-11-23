from collections import defaultdict
from functools import lru_cache
from typing import Protocol

from acex.policies import SoftwarePolicyManager
from acex_devkit.models.compliance import (
    AssetSoftwareCompliance,
    SoftwareCompliance,
    SoftwareComplianceSummary,
    SoftwareStatus,
)
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.policy import SoftwarePolicyCreate, SoftwarePolicyResponse

MEASURED = (SoftwareStatus.golden, SoftwareStatus.accepted, SoftwareStatus.not_allowed)


class Measurable(Protocol):
    """What the check reads of an asset: an asset of the inventory, or a row read for it."""

    vendor: Vendor
    hardware_model: str
    os: OS
    os_version: str | None


@lru_cache(maxsize=4096)
def running_key(os: OS, version: str):
    """`SoftwarePolicyCreate.version_key`, read once for each version: many assets run the same one."""
    return SoftwarePolicyCreate.version_key(os, version)


class ApprovedVersions:
    """The versions the software policy approves, indexed by what an asset is matched on. The policy is read and
    indexed once for every asset a check covers; each asset then finds its versions without going through it all."""

    def __init__(self, policies: list[SoftwarePolicyResponse]):
        # Each version with its key, in the order the policy lists them.
        self._for_model = defaultdict(list)
        self._for_vendor = defaultdict(list)
        for policy in policies:
            version = (SoftwarePolicyCreate.version_key(policy.os, policy.os_version), policy)
            if policy.hardware_model:
                self._for_model[(policy.vendor, policy.os, policy.hardware_model.casefold())].append(version)
            elif policy.hardware_model is None:
                self._for_vendor[(policy.vendor, policy.os)].append(version)

    def covering(self, asset: Measurable) -> list[tuple[object, SoftwarePolicyResponse]]:
        """The versions approved for the asset's model on its OS; where its model has none on that OS, those for
        its vendor on that OS. Each comes with its key. The golden version among them is the one for that OS."""
        for_model = self._for_model.get((asset.vendor, asset.os, asset.hardware_model.casefold()))
        return for_model or self._for_vendor.get((asset.vendor, asset.os), [])


class SoftwareCheck:
    """Software compliance: what each asset of a node runs against the versions the software policy approves for
    its hardware model on the OS it runs, or else for its vendor on that OS. A version not approved is not allowed.
    A policy for another OS does not concern the asset."""

    def __init__(self, policies: SoftwarePolicyManager):
        self.policies = policies

    def approved(self) -> ApprovedVersions:
        """The policy as it stands, read once for every node a check covers."""
        return ApprovedVersions(self.policies.list_policies())

    def node(self, node: NodeInstance, approved: ApprovedVersions) -> SoftwareCompliance:
        """Each asset on its own: a cluster's members are counted one by one."""
        assets = node.asset.assets if node.asset.type == "asset_cluster" else [node.asset]
        results = [self.asset(asset, approved) for asset in assets]
        return SoftwareCompliance(**self.count(results).model_dump(), assets=results)

    def asset(self, asset: Measurable, approved: ApprovedVersions) -> AssetSoftwareCompliance:
        status, golden_version = self.status(asset, approved)
        return AssetSoftwareCompliance(
            asset_id=asset.id,
            hardware_model=asset.hardware_model,
            os=asset.os,
            os_version=asset.os_version,
            status=status,
            golden_version=golden_version,
        )

    @staticmethod
    def status(asset: Measurable, approved: ApprovedVersions) -> tuple[SoftwareStatus, str | None]:
        """What the asset runs against the policy, and the version to aim for where the policy names one. The one
        place the status is decided: a node's compliance and the list of assets both read it from here. It takes the
        index, not the policy as a list: indexing per asset would be slower than the scan it replaces."""
        versions = approved.covering(asset)
        golden = next((policy for _, policy in versions if policy.golden), None)
        golden_version = golden.os_version if golden else None
        if not versions:
            return SoftwareStatus.no_policy, golden_version
        if asset.os_version is None:
            return SoftwareStatus.unknown_version, golden_version
        running = running_key(asset.os, asset.os_version)
        match = next((policy for key, policy in versions if key == running), None)
        if match is None:
            return SoftwareStatus.not_allowed, golden_version
        return (SoftwareStatus.golden if match.golden else SoftwareStatus.accepted), golden_version

    def summarize(self, results: list[SoftwareCompliance]) -> SoftwareComplianceSummary:
        return self.count([asset for result in results for asset in result.assets])

    @staticmethod
    def count(assets: list[AssetSoftwareCompliance]) -> SoftwareComplianceSummary:
        by_status = {status: sum(1 for a in assets if a.status == status) for status in SoftwareStatus}
        measured = sum(by_status[s] for s in MEASURED)
        compliant = by_status[SoftwareStatus.golden] + by_status[SoftwareStatus.accepted]
        return SoftwareComplianceSummary(
            assets_total=len(assets),
            golden_count=by_status[SoftwareStatus.golden],
            accepted_count=by_status[SoftwareStatus.accepted],
            not_allowed_count=by_status[SoftwareStatus.not_allowed],
            no_policy_count=by_status[SoftwareStatus.no_policy],
            unknown_version_count=by_status[SoftwareStatus.unknown_version],
            compliance_percentage=round(compliant / measured * 100, 2) if measured else None,
        )
