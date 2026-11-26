"""Actions a driver can run from a device. Each action has its own params and result model.

Actions are abstract: the same params and result whatever the vendor, so a result never carries the
device's own output. An action troubleshoots or collects data; it never changes the device's
configuration.

ACTIONS lists every action. The API's routes, the client and the MCP tools are all made from it, so an
action added here needs only its driver implementations and the worker's handler besides.
"""

from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, Field, computed_field


class ActionParams(BaseModel):
    """Base for action parameters. `action` names the `Actions` method that runs it.

    The subclass's docstring and field descriptions are what an API reader or a language model sees of
    the action, so they say what it does and what each field means.
    """

    action: ClassVar[str]


class PingParams(ActionParams):
    """Ping a target from the device, to check that it is reachable from there and how fast it answers."""

    action: ClassVar[str] = "ping"
    target: str = Field(min_length=1, description="Address or hostname to ping.")
    count: int = Field(1, ge=1, le=100, description="Packets to send.")
    vrf: str | None = Field(None, description="VRF to ping in; None pings in the global routing table.")
    source: str | None = Field(None, description="Interface to send from.")
    timeout: int = Field(2, ge=1, le=60, description="Seconds to wait for each reply.")
    size: int | None = Field(
        None,
        ge=36,
        le=9216,
        description="Bytes per packet. When set, packets are sent with don't-fragment, so a path's MTU can be checked.",
    )


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


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """One action: its params, its result, and the longest a caller should wait for a node's answer
    before leaving the run to finish on its own."""

    params: type[ActionParams]
    result: type[BaseModel]
    #: Seconds. Covers the action itself plus a worker picking up the job.
    max_wait: int

    @property
    def name(self) -> str:
        return self.params.action

    @property
    def description(self) -> str:
        return (self.params.__doc__ or "").strip()


#: Every action, by name.
ACTIONS: dict[str, ActionSpec] = {
    spec.name: spec
    for spec in [
        ActionSpec(PingParams, PingResult, max_wait=60),
    ]
}
