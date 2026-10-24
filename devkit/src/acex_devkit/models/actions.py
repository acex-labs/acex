"""Actions a driver can run from a device. Each action has its own params and result model.

Actions are abstract: the same params and result whatever the vendor, so a result never carries the
device's own output.
"""

from typing import ClassVar

from pydantic import BaseModel, Field, computed_field


class ActionParams(BaseModel):
    """Base for action parameters. `action` names the `Actions` method that runs it."""

    action: ClassVar[str]


class PingParams(ActionParams):
    action: ClassVar[str] = "ping"
    target: str = Field(min_length=1)
    count: int = Field(1, ge=1, le=100)
    #: None pings in the global routing table.
    vrf: str | None = None
    #: An interface to send from.
    source: str | None = None
    #: Seconds to wait for each reply.
    timeout: int = Field(2, ge=1, le=60)
    #: Bytes per packet. When set, packets are sent with don't-fragment, so a path's MTU can be checked.
    size: int | None = Field(None, ge=36, le=9216)


class PingResult(BaseModel):
    sent: int
    received: int
    #: Round-trip times; None when nothing came back.
    rtt_min_ms: float | None = None
    rtt_avg_ms: float | None = None
    rtt_max_ms: float | None = None

    @computed_field
    @property
    def success_rate(self) -> float:
        """Percent of the packets sent that came back."""
        return round(self.received / self.sent * 100, 1) if self.sent else 0.0

    @computed_field
    @property
    def success(self) -> bool:
        """Every packet came back."""
        return self.sent > 0 and self.received == self.sent
