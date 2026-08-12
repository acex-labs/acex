from pydantic import BaseModel


class ComplianceResult(BaseModel):
    """Compliance summary for a single node instance.

    Shape matches the stripped `Diff.model_dump()` from devkit's configdiffer,
    with the per-component change lists removed.
    """

    total_desired: int = 0
    total_observed: int = 0
    compliant_count: int = 0
    compliance_percentage: float = 0.0


class SiteComplianceResult(BaseModel):
    """Compliance aggregated across all nodes in a site."""

    nodes: dict[int, ComplianceResult] = {}
    summary: ComplianceResult = ComplianceResult()
