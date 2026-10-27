"""The job types the backend creates. Workers hold the code that runs them."""

from acex.jobs.registry import JobType, registry
from acex.operations.kinds import EXECUTE as _EXECUTE
from acex.operations.kinds import OPERATIONS
from acex.workflows.job_types import (
    WORKFLOW_NODE_STEPS,
    WORKFLOW_ONCE_STEPS,
    WorkflowWait,
)
from acex.workflows.job_types import WORKFLOW_RUN as _WORKFLOW_RUN
from acex.ztp.discovery import record_discovery
from acex.ztp.pipeline_view import ZTP_PROVISION as _ZTP_PROVISION
from acex_devkit.models.cve import CveDiscoverData, CveDiscoverResult
from acex_devkit.models.job import JobSubjectType
from acex_devkit.models.workflows import (
    WorkflowNodeJob,
    WorkflowNodeResult,
    WorkflowRunData,
    WorkflowStepJob,
    WorkflowStepResult,
    WorkflowWaitJob,
)
from acex_devkit.models.ztp import (
    ZtpDiscoverData,
    ZtpDiscoverResult,
    ZtpProvisionData,
    ZtpProvisionResult,
)

#: Log in to a device that fetched its ZTP bootstrap and find out what it is.
#: What it reports is recorded as a discovery for an administrator to review.
ZTP_DISCOVER = registry.register(
    JobType(
        "acex.ztp.discover",
        data=ZtpDiscoverData,
        result=ZtpDiscoverResult,
        on_succeeded=record_discovery,
    )
)

#: Push full configuration to a node whose device has been approved, and verify it.
ZTP_PROVISION = registry.register(
    JobType(
        _ZTP_PROVISION,
        data=ZtpProvisionData,
        result=ZtpProvisionResult,
        subject=(JobSubjectType.node, "node_id"),
    )
)

#: Operations on a node: raw commands, and each abstract action. Run on a node and report what it
#: answered; raw output is masked by its NED.
for _operation in OPERATIONS.values():
    registry.register(
        JobType(
            _operation.job_type,
            data=_operation.data,
            result=_operation.result,
            subject=(JobSubjectType.node, "node_id"),
        )
    )
EXECUTE = registry.get(_EXECUTE.job_type)

#: A workflow run. The backend keeps its state as it starts the steps' jobs under it.
WORKFLOW_RUN = registry.register(
    JobType(
        _WORKFLOW_RUN,
        data=WorkflowRunData,
        subject=(JobSubjectType.workflow, "workflow_id"),
        orchestrated=True,
    )
)

#: The steps of a workflow run. A step on nodes runs one job per node, rendering its templates for that node; the
#: others run once. Each reports what it did and the artifacts it leaves.
for _job_type in WORKFLOW_NODE_STEPS.values():
    registry.register(
        JobType(
            _job_type,
            data=WorkflowNodeJob,
            result=WorkflowNodeResult,
            subject=(JobSubjectType.node, "node_id"),
        )
    )
for _step_type, _job_type in WORKFLOW_ONCE_STEPS.items():
    if _step_type == "wait":
        # Run by the backend when its time has come, holding no worker meanwhile.
        registry.register(
            JobType(
                _job_type,
                data=WorkflowWaitJob,
                result=WorkflowStepResult,
                local=WorkflowWait.elapsed,
            )
        )
    else:
        registry.register(
            JobType(_job_type, data=WorkflowStepJob, result=WorkflowStepResult)
        )

CVE_DISCOVER = registry.register(
    JobType("acex.cve.discover", data=CveDiscoverData, result=CveDiscoverResult)
)
