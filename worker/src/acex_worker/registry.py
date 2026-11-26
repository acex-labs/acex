"""
Handler registry. Defines a mapping between job type and handler
class to handle the job event.
"""

from acex_devkit.models.actions import ACTIONS

from acex_worker.handlers.cve_discovery import CveDiscoveryHandler
from acex_worker.handlers.execute import HandleAction, HandleExecute
from acex_worker.handlers.patch import HandlePatchApply, HandlePatchRender
from acex_worker.handlers.workflow import (
    HandleWorkflowAction,
    HandleWorkflowAssert,
    HandleWorkflowCompute,
    HandleWorkflowCondition,
    HandleWorkflowExecute,
    HandleWorkflowProbe,
    HandleWorkflowProbeAddress,
)
from acex_worker.handlers.ztp_discover import HandleZtpDiscovery
from acex_worker.handlers.ztp_provision import HandleZtpProvision

HANDLERS = {
    "acex.ztp.discover": HandleZtpDiscovery,
    "acex.ztp.provision": HandleZtpProvision,
    "acex.operations.execute": HandleExecute,
    **{f"{HandleAction.PREFIX}{name}": HandleAction for name in ACTIONS},
    "acex.operations.patch.render": HandlePatchRender,
    "acex.operations.patch.apply": HandlePatchApply,
    "acex.operations.workflow.execute": HandleWorkflowExecute,
    "acex.operations.workflow.action": HandleWorkflowAction,
    "acex.operations.workflow.probe": HandleWorkflowProbe,
    "acex.operations.workflow.probe.address": HandleWorkflowProbeAddress,
    "acex.operations.workflow.compute": HandleWorkflowCompute,
    "acex.operations.workflow.assert": HandleWorkflowAssert,
    "acex.operations.workflow.condition": HandleWorkflowCondition,
    "acex.cve.discover": CveDiscoveryHandler,
}
