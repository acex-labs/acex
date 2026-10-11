"""The job types the backend creates. Workers hold the code that runs them."""

from acex.jobs.registry import JobType, registry
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
