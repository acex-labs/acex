"""The job types the backend creates. Workers hold the code that runs them."""

from acex.jobs.registry import JobType, registry
from acex_devkit.models.ztp import ZtpDiscoverData

#: Log in to a device that fetched its ZTP bootstrap and find out what it is.
ZTP_DISCOVER = registry.register(JobType("acex.ztp.discover", data=ZtpDiscoverData))
