from typing import ClassVar, Optional

from acex.observability.capability import TelemetryCapability
from acex.observability.components.base import TelemetryComponent

# Standard OIDs polled for every SNMP-capable node
_FIELDS = [
    {"oid": "1.3.6.1.2.1.1.3.0", "name": "uptime"},
    {"oid": "1.3.6.1.2.1.1.5.0", "name": "source", "is_tag": True},
]


class SnmpTelemetry(TelemetryComponent):
    kind: ClassVar[str] = "snmp"
    measurement: ClassVar[str] = "snmp"
    capability: ClassVar[Optional[TelemetryCapability]] = TelemetryCapability.snmp

    def __init__(
        self,
        node_id: int,
        hostname: str,
        target_ip: str,
        site: Optional[str] = None,
        region: Optional[str] = None,
        community: str = "public",
    ):
        self.node_id = node_id
        self.hostname = hostname
        self.target_ip = target_ip
        self.site = site
        self.region = region
        self.community = community

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
        if self.region:
            tags["region"] = self.region
        return tags

    def telegraf_input(self) -> Optional[dict]:
        return {
            "plugin": "snmp",
            "config": {
                "agents": [f"udp://{self.target_ip}:161"],
                "name": self.hostname,
                "version": 2,
                "community": self.community,
            },
            "tags": self.tags(),
            "subtables": [{"name": "field", "data": field} for field in _FIELDS],
        }
