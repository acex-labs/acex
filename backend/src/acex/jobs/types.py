"""The job types the backend creates. Workers hold the code that runs them."""

from acex.jobs.registry import JobType, registry
from acex.operations.kinds import EXECUTE as _EXECUTE
from acex.operations.kinds import OPERATIONS
from acex.ztp.discovery import record_discovery
from acex.ztp.pipeline_view import ZTP_PROVISION as _ZTP_PROVISION
from acex_devkit.models.job import JobSubjectType
from acex_devkit.models.ztp import ZtpDiscoverData, ZtpDiscoverResult, ZtpProvisionData, ZtpProvisionResult

#: Log in to a device that fetched its ZTP bootstrap and find out what it is.
#: What it reports is recorded as a discovery for an administrator to review.
ZTP_DISCOVER = registry.register(
    JobType("acex.ztp.discover", data=ZtpDiscoverData, result=ZtpDiscoverResult, on_succeeded=record_discovery)
)

#: Push full configuration to a node whose device has been approved, and verify it.
ZTP_PROVISION = registry.register(
    JobType(_ZTP_PROVISION, data=ZtpProvisionData, result=ZtpProvisionResult, subject=(JobSubjectType.node, "node_id"))
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
