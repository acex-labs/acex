"""
Handler registry. Defines a mapping between job type and handler
class to handle the job event.
"""

from acex_worker.handlers.ztp_discover import HandleZtpDiscovery
from acex_worker.handlers.ztp_provision import HandleZtpProvision

HANDLERS = {
    "acex.ztp.discover": HandleZtpDiscovery,
    "acex.ztp.provision": HandleZtpProvision,
}
