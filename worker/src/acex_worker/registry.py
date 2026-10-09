"""
Handler registry. Defines a mapping between job type and handler
class to handle the job event.
"""

from acex_worker.handlers.ztp_discover import HandleZtpDiscovery

HANDLERS = {
    "acex.ztp.discover": HandleZtpDiscovery,
}
