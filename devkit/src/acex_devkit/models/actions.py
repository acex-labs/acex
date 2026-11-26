"""Actions a driver can run from a device. Each action has its own params and result model.

Actions are abstract: the same params and result whatever the vendor, so a result never carries the
device's own output. An action troubleshoots or collects data; it never changes the device's
configuration.

The shared conventions: interface names are as the device writes them, never translated; a MAC address
is `aa:bb:cc:dd:ee:ff` whatever the device prints; a VRF of None is the global routing table; ages are
in seconds; a lookup that finds nothing says so in its result rather than failing.

ACTIONS lists every action. The API's routes, the client, the MCP tools and the worker are all made from
it, so an action added here needs only its driver implementations besides.
"""

import re
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Annotated, Any, ClassVar, Literal, Self, get_args

from pydantic import BaseModel, BeforeValidator, Field, computed_field


class MacFormat:
    """Any common way of writing a MAC address, read as `aa:bb:cc:dd:ee:ff`."""

    SEPARATORS = re.compile(r"[.:\-]")
    DIGITS = re.compile(r"[0-9a-f]{12}")

    @classmethod
    def normalize(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        digits = cls.SEPARATORS.sub("", value.strip().lower())
        if not cls.DIGITS.fullmatch(digits):
            raise ValueError(f"{value!r} is not a MAC address")
        return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


#: A MAC address as `aa:bb:cc:dd:ee:ff`. `0050.56a1.2b3c`, `00-50-56-A1-2B-3C` and the like are read into it.
MacAddress = Annotated[str, BeforeValidator(MacFormat.normalize)]


class ActionParams(BaseModel):
    """Base for action parameters. `action` names the `Actions` method that runs it.

    The subclass's docstring and field descriptions are what an API reader or a language model sees of
    the action, so they say what it does and what each field means.
    """

    action: ClassVar[str]


class TableParams(ActionParams):
    """Params of an action that reads a table, which can be long."""

    max_entries: int | None = Field(
        None,
        ge=1,
        description="Return at most this many rows. The result says how many there were and whether it was cut.",
    )


class RowsResult(BaseModel):
    """A result whose substance is a list of rows, the field `rows` names. A run's report gives each row a
    line of its own."""

    rows: ClassVar[str]


class TableResult(RowsResult):
    """A table read from the device. Drivers return every row; `Session.run_action` cuts it to the
    caller's `max_entries` and fills in `total` and `truncated`."""

    total: int = Field(0, description="Rows the device returned, before any were cut.")
    truncated: bool = Field(False, description="Rows were cut at max_entries.")

    def limit(self, max_entries: int | None) -> Self:
        rows = getattr(self, self.rows)
        cut = max_entries is not None and len(rows) > max_entries
        return self.model_copy(
            update={"total": len(rows), "truncated": cut, self.rows: rows[:max_entries] if cut else rows}
        )


# ---------------------------------------------------------------------------------------------------- ping


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


# ------------------------------------------------------------------------------------------- MAC addresses


class MacEntry(BaseModel):
    """One MAC address learned or set in one VLAN on one interface. An address in several VLANs, or on
    several interfaces, is one entry for each."""

    mac: MacAddress
    vlan: int | None = Field(None, description="None where the device's table has no VLAN for the entry.")
    interface: str = Field(description="As the device names it; CPU for the device's own addresses.")
    type: Literal["dynamic", "static", "other"]


class MacAddressTableParams(TableParams):
    """Read the device's MAC address table, to see which addresses it has learned and on which interfaces."""

    action: ClassVar[str] = "get_mac_address_table"
    vlan: int | None = Field(None, ge=1, le=4094, description="Only this VLAN; None reads every VLAN.")
    interface: str | None = Field(None, description="Only this interface, as the device names it.")


class MacAddressTableResult(TableResult):
    rows: ClassVar[str] = "entries"
    entries: list[MacEntry]


class LookupMacAddressParams(ActionParams):
    """Find where the device has learned one MAC address: in which VLANs and on which interfaces. Following
    it switch by switch shows where the address enters a layer 2 domain."""

    action: ClassVar[str] = "lookup_mac_address"
    mac: MacAddress = Field(description="The address, written any common way.")
    vlans: list[int] | None = Field(
        None, description="Look only in these VLANs; None looks in every VLAN. Some platforms answer faster with them."
    )


class LookupMacAddressResult(RowsResult):
    rows: ClassVar[str] = "entries"
    mac: MacAddress
    entries: list[MacEntry]

    @computed_field
    @property
    def found(self) -> bool:
        """The device has the address in at least one VLAN."""
        return bool(self.entries)


# ---------------------------------------------------------------------------------------------- IP routes


class NextHop(BaseModel):
    address: IPv4Address | None = Field(None, description="None for a route out of an interface, e.g. connected.")
    interface: str | None = Field(None, description="As the device names it; None where the device doesn't say.")


class Route(BaseModel):
    prefix: IPv4Network
    protocol: Literal["connected", "local", "static", "ospf", "bgp", "eigrp", "isis", "rip", "other"]
    subtype: (
        Literal[
            "intra_area",
            "inter_area",
            "external_1",
            "external_2",
            "nssa_1",
            "nssa_2",
            "internal",
            "external",
            "level_1",
            "level_2",
        ]
        | None
    ) = Field(None, description="OSPF area or external type, BGP internal or external, IS-IS level.")
    distance: int | None = Field(None, description="Administrative distance; None where the device doesn't show it.")
    metric: int | None = None
    age_seconds: int | None = Field(None, description="Since the route was installed; None where not shown.")
    next_hops: list[NextHop] = Field(description="Several for a route shared over equal-cost paths.")


class IpRouteParams(TableParams):
    """Read the device's IPv4 routing table, or look up how it routes one address or prefix."""

    action: ClassVar[str] = "get_ip_route"
    prefix: IPv4Address | IPv4Network | None = Field(
        None,
        description="An address finds the route it uses (longest match); a prefix, e.g. 10.0.0.0/24, finds that "
        "route exactly. None reads the whole table.",
    )
    vrf: str | None = Field(None, description="VRF to read; None reads the global routing table.")


class IpRouteResult(TableResult):
    rows: ClassVar[str] = "routes"
    vrf: str | None = None
    routes: list[Route] = Field(description="Empty when there is no route.")


# -------------------------------------------------------------------------------------------------- ARP


class ArpEntry(BaseModel):
    ip: IPv4Address
    mac: MacAddress | None = Field(None, description="None while the entry is incomplete.")
    interface: str | None = Field(None, description="As the device names it.")
    age_seconds: int | None = Field(None, description="None for a static entry or the device's own address.")
    type: Literal["dynamic", "static", "incomplete"] = Field(
        description="static includes the device's own addresses; incomplete is asked for but not answered."
    )


class ArpTableParams(TableParams):
    """Read the device's ARP table: which MAC address answers for each IP address on its networks."""

    action: ClassVar[str] = "get_arp_table"
    vrf: str | None = Field(None, description="VRF to read; None reads the global table.")
    interface: str | None = Field(None, description="Only this interface, as the device names it.")


class ArpTableResult(TableResult):
    rows: ClassVar[str] = "entries"
    vrf: str | None = None
    entries: list[ArpEntry]


class LookupArpParams(ActionParams):
    """Look up the ARP entry for one IP address: which MAC address answers for it, and on which interface."""

    action: ClassVar[str] = "lookup_arp"
    ip: IPv4Address = Field(description="The IPv4 address to look up.")
    vrf: str | None = Field(None, description="VRF to look in; None looks in the global table.")


class LookupArpResult(BaseModel):
    ip: IPv4Address
    vrf: str | None = None
    entry: ArpEntry | None = None

    @computed_field
    @property
    def found(self) -> bool:
        """The device has an entry for the address, if only an incomplete one."""
        return self.entry is not None


# ------------------------------------------------------------------------------------------- traceroute


class TracerouteParams(ActionParams):
    """Trace the path from the device to a target, hop by hop. Hops are shown as addresses, never names."""

    action: ClassVar[str] = "traceroute"
    target: str = Field(min_length=1, description="Address or hostname to trace to.")
    vrf: str | None = Field(None, description="VRF to trace in; None traces in the global routing table.")
    source: str | None = Field(None, description="Interface to send from.")
    max_hops: int = Field(30, ge=1, le=64, description="Give up after this many hops.")
    probes: int = Field(3, ge=1, le=10, description="Probes sent to each hop.")
    timeout: int = Field(2, ge=1, le=10, description="Seconds to wait for each probe.")


class TracerouteProbe(BaseModel):
    address: IPv4Address | None = Field(None, description="Who answered; None when nothing did.")
    rtt_ms: float | None = None
    unreachable: Literal["host", "network", "protocol", "admin", "other"] | None = Field(
        None, description="The answer was that the target can't be reached, and why."
    )


class TracerouteHop(BaseModel):
    ttl: int
    probes: list[TracerouteProbe]


class TracerouteResult(RowsResult):
    rows: ClassVar[str] = "hops"
    destination: IPv4Address | None = Field(None, description="The address traced to; None if it didn't resolve.")
    hops: list[TracerouteHop]

    @computed_field
    @property
    def reached(self) -> bool:
        """The destination itself answered."""
        return self.destination is not None and any(
            probe.address == self.destination for hop in self.hops[-1:] for probe in hop.probes
        )


# ------------------------------------------------------------------------------------------ interfaces


class InterfaceStatus(BaseModel):
    """One interface's state and error counters. Counters add up from when they were last cleared, so it is
    the change between two readings that tells."""

    name: str = Field(description="As the device names it.")
    description: str | None = None
    admin_status: Literal["up", "down"]
    oper_status: Literal["up", "down", "err_disabled"]
    speed_mbps: int | None = Field(None, description="None when not negotiated, or not applicable.")
    duplex: Literal["full", "half"] | None = Field(None, description="None when not negotiated, or not applicable.")
    input_errors: int | None = None
    output_errors: int | None = None
    input_discards: int | None = None
    output_discards: int | None = None


class InterfaceStatusParams(TableParams):
    """Read the status of the device's interfaces: up or down, speed and duplex, and error and discard counters."""

    action: ClassVar[str] = "get_interface_status"
    interface: str | None = Field(None, description="Only this interface, as the device names it; None reads all.")


class InterfaceStatusResult(TableResult):
    rows: ClassVar[str] = "interfaces"
    interfaces: list[InterfaceStatus]


# ---------------------------------------------------------------------------------------------- the list


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """One action: its params, its result, a short name for it in a user interface, and the longest a caller
    should wait for a node's answer before leaving the run to finish on its own."""

    params: type[ActionParams]
    result: type[BaseModel]
    label: str
    #: Seconds. Covers the action itself plus a worker picking up the job.
    max_wait: int

    @property
    def name(self) -> str:
        return self.params.action

    @property
    def description(self) -> str:
        return (self.params.__doc__ or "").strip()

    @property
    def rows(self) -> str | None:
        """The result's field holding its rows, when it is made of rows."""
        return self.result.rows if issubclass(self.result, RowsResult) else None

    @property
    def columns(self) -> list[str]:
        """A row's fields when the result is made of rows, otherwise the result's."""
        shape = get_args(self.result.model_fields[self.rows].annotation)[0] if self.rows else self.result
        return [*shape.model_fields, *shape.model_computed_fields]

    @property
    def fields(self) -> list[str]:
        """The result's own fields."""
        return [*self.result.model_fields, *self.result.model_computed_fields]


class ActionInfo(BaseModel):
    """An action as the API lists it, for a client to build its form and show its result from."""

    name: str
    label: str
    description: str
    max_wait: int
    #: JSON schemas of the params and the result.
    params: dict[str, Any]
    result: dict[str, Any]
    #: The result's field holding its rows, when it is made of rows.
    rows: str | None
    #: A row's fields, or the result's when it has no rows.
    columns: list[str]

    @classmethod
    def of(cls, spec: ActionSpec) -> "ActionInfo":
        return cls(
            name=spec.name,
            label=spec.label,
            description=spec.description,
            max_wait=spec.max_wait,
            params=spec.params.model_json_schema(),
            result=spec.result.model_json_schema(mode="serialization"),
            rows=spec.rows,
            columns=spec.columns,
        )


#: Every action, by name.
ACTIONS: dict[str, ActionSpec] = {
    spec.name: spec
    for spec in [
        ActionSpec(PingParams, PingResult, label="Ping", max_wait=60),
        ActionSpec(MacAddressTableParams, MacAddressTableResult, label="MAC address table", max_wait=60),
        ActionSpec(LookupMacAddressParams, LookupMacAddressResult, label="Lookup MAC", max_wait=60),
        ActionSpec(IpRouteParams, IpRouteResult, label="IP route", max_wait=60),
        ActionSpec(ArpTableParams, ArpTableResult, label="ARP table", max_wait=60),
        ActionSpec(LookupArpParams, LookupArpResult, label="Lookup ARP", max_wait=60),
        ActionSpec(TracerouteParams, TracerouteResult, label="Traceroute", max_wait=120),
        ActionSpec(InterfaceStatusParams, InterfaceStatusResult, label="Interface status", max_wait=60),
    ]
}
