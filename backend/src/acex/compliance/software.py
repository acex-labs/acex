from acex.policies import SoftwarePolicyManager
from acex_devkit.models.asset import AssetResponse
from acex_devkit.models.compliance import (
    AssetSoftwareCompliance,
    SoftwareCompliance,
    SoftwareComplianceSummary,
    SoftwareStatus,
)
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.policy import SoftwarePolicyCreate, SoftwarePolicyResponse

MEASURED = (SoftwareStatus.golden, SoftwareStatus.accepted, SoftwareStatus.not_allowed)


class SoftwareCheck:
    """Software compliance: what each asset of a node runs against the versions the software policy approves for
    its hardware model, or else its vendor. A version not approved is not allowed."""

    def __init__(self, policies: SoftwarePolicyManager):
        self.policies = policies

    def approved(self) -> list[SoftwarePolicyResponse]:
        """The policy as it stands, read once for every node a check covers."""
        return self.policies.list_policies()

    def node(self, node: NodeInstance, approved: list[SoftwarePolicyResponse]) -> SoftwareCompliance:
        """Each asset on its own: a cluster's members are counted one by one."""
        assets = node.asset.assets if node.asset.type == "asset_cluster" else [node.asset]
        results = [self.asset(asset, approved) for asset in assets]
        return SoftwareCompliance(**self.count(results).model_dump(), assets=results)

    def asset(self, asset: AssetResponse, approved: list[SoftwarePolicyResponse]) -> AssetSoftwareCompliance:
        versions = self.covering(asset, approved)
        golden = next((v for v in versions if v.golden), None)
        result = AssetSoftwareCompliance(
            asset_id=asset.id,
            hardware_model=asset.hardware_model,
            os=asset.os,
            os_version=asset.os_version,
            status=SoftwareStatus.no_policy,
            golden_version=golden.os_version if golden else None,
        )
        if not versions:
            return result
        if asset.os_version is None:
            return result.model_copy(update={"status": SoftwareStatus.unknown_version})
        running = (asset.os, SoftwarePolicyCreate.version_key(asset.os, asset.os_version))
        match = next(
            (v for v in versions if (v.os, SoftwarePolicyCreate.version_key(v.os, v.os_version)) == running), None
        )
        if match is None:
            return result.model_copy(update={"status": SoftwareStatus.not_allowed})
        status = SoftwareStatus.golden if match.golden else SoftwareStatus.accepted
        return result.model_copy(update={"status": status})

    @staticmethod
    def covering(asset: AssetResponse, approved: list[SoftwarePolicyResponse]) -> list[SoftwarePolicyResponse]:
        """The versions approved for the asset's model; where its model has none, those for its vendor."""
        vendor = [v for v in approved if v.vendor == asset.vendor]
        for_model = [
            v for v in vendor if v.hardware_model and v.hardware_model.casefold() == asset.hardware_model.casefold()
        ]
        return for_model or [v for v in vendor if v.hardware_model is None]

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
