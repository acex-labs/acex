import asyncio
import logging

from acex.config_diff import DiffLogicalNode
from acex_devkit.exceptions import DriverException
from acex_devkit.models.compliance import (
    ConfigurationCompliance,
    ConfigurationComplianceSummary,
    ConfigurationStatus,
)
from fastapi import HTTPException

log = logging.getLogger(__name__)


class ConfigurationCheck:
    """Configuration compliance: a node's logical node diff, and summaries over many nodes."""

    def __init__(self, differ: DiffLogicalNode):
        self.differ = differ

    async def node(self, node_instance_id: str) -> ConfigurationCompliance:
        try:
            observed = await self.differ.observed(node_instance_id)
            await asyncio.sleep(0)  # parsing is the longest step; let the server answer before the comparison
        except HTTPException:
            raise
        except DriverException as exc:
            # A driver that cannot parse (Junos has no parser yet) leaves the node unmeasured, and that is not an error.
            log.debug("Node %s is not measured: %s", node_instance_id, exc)
            observed = None
        except Exception:
            # A configuration its NED cannot parse is as good as none: this node is not measured, the others are.
            log.exception("Could not parse the observed configuration of node %s", node_instance_id)
            observed = None
        if observed is None:
            return ConfigurationCompliance(status=ConfigurationStatus.not_collected)
        diff = await self.differ.diff_against(node_instance_id, observed)
        return ConfigurationCompliance(
            status=ConfigurationStatus.measured,
            total_desired=diff.total_desired,
            total_observed=diff.total_observed,
            compliant_count=diff.compliant_count,
            undeclared_count=diff.undeclared_count,
            unparsed_count=diff.unparsed_count,
            compliance_percentage=diff.compliance_percentage,
        )

    def summarize(self, results: list[ConfigurationCompliance]) -> ConfigurationComplianceSummary:
        """Sums over the measured nodes; the ones not collected are only counted."""
        measured = [r for r in results if r.status == ConfigurationStatus.measured]
        desired = sum(r.total_desired for r in measured)
        compliant = sum(r.compliant_count for r in measured)
        percentage = None
        if measured:
            percentage = round(compliant / desired * 100, 2) if desired else 100.0
        return ConfigurationComplianceSummary(
            nodes_total=len(results),
            nodes_not_collected=len(results) - len(measured),
            total_desired=desired,
            total_observed=sum(r.total_observed for r in measured),
            compliant_count=compliant,
            undeclared_count=sum(r.undeclared_count for r in measured),
            unparsed_count=sum(r.unparsed_count for r in measured),
            compliance_percentage=percentage,
        )
