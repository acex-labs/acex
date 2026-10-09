"""The job types the backend creates. Workers hold the code that runs them."""

from acex.jobs.registry import JobType, registry
from acex.ztp.discovery import record_discovery
from acex_devkit.models.ztp import ZtpDiscoverData, ZtpDiscoverResult

#: Log in to a device that fetched its ZTP bootstrap and find out what it is.
#: What it reports is recorded as a discovery for an administrator to review.
ZTP_DISCOVER = registry.register(
    JobType("acex.ztp.discover", data=ZtpDiscoverData, result=ZtpDiscoverResult, on_succeeded=record_discovery)
)
