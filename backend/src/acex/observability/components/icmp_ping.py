from typing import ClassVar, Optional

from acex.observability.capability import TelemetryCapability
from acex.observability.components.base import TelemetryComponent


class IcmpPingTelemetry(TelemetryComponent):
    """
    ICMP ping observation for a single node-instance.

    Maps to telegraf's `[[inputs.ping]]` plugin and writes the standard
    `ping` measurement to InfluxDB. We attach `node`, `node_id`, and `site`
    as input-level tags so dashboards can filter on logical metadata
    instead of raw IP.
    """

    kind: ClassVar[str] = "icmp_ping"
    measurement: ClassVar[str] = "ping"
    capability: ClassVar[Optional[TelemetryCapability]] = TelemetryCapability.icmp

    def __init__(
        self,
        node_id: int,
        hostname: str,
        target_ip: str,
        site: Optional[str] = None,
    ):
        self.node_id = node_id
        self.hostname = hostname
        self.target_ip = target_ip
        self.site = site

    def target_id(self) -> str:
        return f"node:{self.node_id}"

    def target_node(self) -> Optional[int]:
        return self.node_id

    def tags(self) -> dict[str, str]:
        tags = {
            "node": self.hostname,
            "node_id": str(self.node_id),
        }
        if self.site:
            tags["site"] = self.site
        return tags

    def telegraf_input(self) -> Optional[dict]:
        return {
            "plugin": "ping",
            "config": {
                "urls": [self.target_ip],
                "count": 3,
                "ping_interval": 1.0,
                "timeout": 5.0,
            },
            "tags": self.tags(),
        }
