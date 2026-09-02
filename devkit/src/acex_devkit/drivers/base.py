"""Driver base classes for ACE-X network element drivers."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any

from acex_devkit.configdiffer import Diff
from acex_devkit.models.management_connection import ManagementConnection
from acex_devkit.models.node_response import NodeListItem
from acex_devkit.normalizer import BaseNormalizer


class ParserBase(ABC):
    """Base class for configuration parsers."""

    @abstractmethod
    def parse(self, configuration: str) -> Any:
        """Parse device configuration into a structured model.

        Args:
            configuration: Raw configuration string from device

        Returns:
            Parsed configuration model
        """
        pass

    mapper: Any = None
    """Set by dialect/attribute-map-based parsers to the same kind of `Mapper` instance the
    renderer uses (see `RendererBase.mapper`) — same free capability reporting, mirrored here so
    it's discoverable from whichever side (renderer or parser) actually built one."""


class RendererBase(ABC):
    """Base class for configuration renderers."""

    @abstractmethod
    def render(self, model: dict[str, Any], asset: Any = None) -> Any:
        """Render configuration model to device-specific format.

        Args:
            model: Device-agnostic configuration model
            asset: Optional asset context

        Returns:
            Device-specific configuration (e.g., string, XML tree)
        """
        pass

    def render_patch(self, diff: Diff, node_instance: Any) -> Any:
        """Render device commands for a config diff. Not yet implemented by every driver, but —
        unlike `TransportBase.execute` or `ObservabilityBase`'s hooks — this isn't reported
        through `NetworkElementDriver.capabilities`: every driver is expected to grow one
        eventually, so it's a maturity gap rather than a capability a caller should branch on."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement render_patch()")

    mapper: Any = None
    """Set by dialect/attribute-map-based renderers (see `acex_devkit.drivers.mapper.Mapper`) to
    the `Mapper` instance driving `render()`. `NetworkElementDriver.capabilities` reads
    `mapper.supported_components()` off this to report which configuration components the driver
    actually supports — entirely derived from the dialect's own attribute maps, so a driver
    author gets it for free just by building `self.mapper` to do the rendering. Renderers that
    don't use `Mapper` (template-based, or a REST-driven dialect) simply leave this `None`, and
    the driver reports no configuration components — an honest default, since there's no
    declarative source to derive them from."""


class TransportBase(ABC):
    """Base class for device transport/communication.

    Each method is self-contained, but transports may also expose
    `session()` as a context manager so a caller can run multiple
    operations against the same physical connection.

    Args:
        node: The node instance (identity, hostname, vendor, os, ned_id)
        connection: Management connection (target_ip, connection_type)
        **kwargs: Future use (credentials, options, etc.)
    """

    OPTIONAL_METHODS: tuple[str, ...] = ("session", "execute")
    """Connectivity hooks a transport may opt into, beyond the mandatory `get_config`/
    `send_config` — moving bytes/commands to and from a device, nothing vendor-specific about
    *interpreting* them. `session` has a working no-op default (a driver that skips it just loses
    connection reuse); `execute` defaults to `raise NotImplementedError`.
    `NetworkElementDriver.capabilities["transport"]` walks this list and reports exactly the ones
    a concrete transport overrides. Turning a device's raw output into structured operational
    data (LLDP neighbors, routing table, ...) is `ObservabilityBase`'s job, not this class's —
    see there."""

    @contextmanager
    def session(self, connection: ManagementConnection, **kwargs):
        """Open a reusable session for multiple ops on one device.

        Default is a no-op: methods continue to open/close per call.
        Drivers that benefit from connection reuse override this to
        hold a single connection open for the duration of the block.
        """
        yield self

    @abstractmethod
    def get_config(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> str:
        """Fetch the full running configuration from a device."""
        pass

    @abstractmethod
    def send_config(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> str:
        """Apply configuration commands to a device."""
        pass

    def execute(self, node: NodeListItem, connection: ManagementConnection, commands: list[str], **kwargs) -> list[str]:
        """Run arbitrary commands and return raw output per command. Opt-in per driver."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement execute()")


class ObservabilityBase:
    """Base class for turning a device's operational output into structured, vendor-agnostic
    data — the observability-side counterpart to `ParserBase`, which does the same job for
    configuration text. Given the driver's `transport` (for issuing whatever show/operational
    commands each hook needs, typically via `transport.execute`), each method here owns both
    "what to ask the device" and "how to make sense of the answer" — that parsing is exactly what
    doesn't belong on `TransportBase`.

    Entirely opt-in: a driver with no operational-data support at all simply leaves
    `NetworkElementDriver.observability_class` unset. Of the hooks it does implement, none are
    mandatory either — a platform might expose routing tables but not ARP, or vice versa — so
    every method here defaults to `raise NotImplementedError` rather than being abstract.
    """

    OPTIONAL_METHODS: tuple[str, ...] = (
        "get_lldp_neighbors",
        "get_arp_table",
        "get_routing_table",
        "ping",
    )
    """Which methods below are opt-in. `NetworkElementDriver.capabilities["observability"]` walks
    this list and reports exactly the ones a concrete subclass overrides — so adding a new kind of
    operational data (e.g. a MAC-address-table fetch) is one edit: define it below with its
    `NotImplementedError` default, add its name here. Nothing else in the framework changes."""

    def __init__(self, transport: TransportBase):
        self.transport = transport

    def get_lldp_neighbors(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        """Fetch LLDP/CDP neighbor table from a device.

        Returns list of dicts with keys:
            local_interface, remote_device, remote_interface, discovery_protocol
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement get_lldp_neighbors()")

    def get_arp_table(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        """Fetch the ARP (IPv4) / neighbor (IPv6) table from a device.

        Returns list of dicts with keys:
            ip_address, mac_address, interface, [state]
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement get_arp_table()")

    def get_routing_table(self, node: NodeListItem, connection: ManagementConnection, **kwargs) -> list[dict]:
        """Fetch the routing table (RIB) from a device.

        Returns list of dicts with keys:
            prefix, next_hop, interface, protocol, [metric], [distance]
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement get_routing_table()")

    def ping(self, node: NodeListItem, connection: ManagementConnection, target: str, **kwargs) -> dict:
        """Run a reachability probe (ICMP ping) for `target`, sourced from the device.

        Returns a dict with keys:
            sent, received, loss_percent, [rtt_min_ms, rtt_avg_ms, rtt_max_ms]
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not implement ping()")


def _overrides_default(component: Any, method_name: str, base_cls: type) -> bool:
    """Whether `component`'s class actually implements `method_name`, rather than just
    inheriting `base_cls`'s opt-in default (a `raise NotImplementedError` stub, or — for
    `TransportBase.session` — a working but no-op fallback)."""
    if component is None:
        return False
    impl = getattr(type(component), method_name, None)
    default = getattr(base_cls, method_name, None)
    return impl is not None and impl is not default


class NetworkElementDriver:
    """Base class for network element drivers.

    Combines up to five independent facades — renderer, parser, transport, normalizer,
    observability — each entirely optional: a driver declares only the ones it has, and any
    unset `*_class` leaves that facade `None` on the instance. `capabilities` (below) is what
    checks that a set facade actually follows the matching base class's interface — an
    `isinstance` check against `RendererBase`/`ParserBase`/`TransportBase`/`BaseNormalizer`/
    `ObservabilityBase` doubles as the "is it even configured" check, since `None` isn't an
    instance of anything.

    Attributes:
        renderer_class: Optional `RendererBase` subclass — renders configuration.
        parser_class: Optional `ParserBase` subclass — parses device configuration.
        transport_class: Optional `TransportBase` subclass — talks to the device.
        normalizer_class: Optional normalizer class for stripping non-intent config and masking
            secrets.
        observability_class: Optional `ObservabilityBase` subclass for structured operational
            data (LLDP, routing table, ...).
    """

    renderer_class = None
    parser_class = None
    transport_class = None
    normalizer_class = None
    observability_class = None

    def __init__(self):
        """Build whichever facades this driver declares; leave the rest `None`."""
        if self.renderer_class is not None:
            self.renderer = self.renderer_class()
        else:
            self.renderer = None

        if self.parser_class is not None:
            self.parser = self.parser_class()
        else:
            self.parser = None

        if self.transport_class is not None:
            self.transport = self.transport_class()
        else:
            self.transport = None

        if self.normalizer_class is not None:
            self.normalizer = self.normalizer_class()
        else:
            self.normalizer = None

        if self.observability_class is not None:
            self.observability = self.observability_class(self.transport)
        else:
            self.observability = None

    @property
    def capabilities(self) -> dict[str, Any]:
        """What this driver actually supports, keyed by facade — a driver can have rich
        observability but no configuration support at all (e.g. a Meraki/ACI-style API driver),
        or vice versa, since each facade is independently optional:

        - `"renderer"` / `"parser"`: `{"active": bool, "configuration": [...]}` — `configuration`
          lists which components (by dotted `ComposedConfiguration` path) that facade covers at
          all, e.g. `["interfaces", "system.config"]` — a component with any coverage is listed
          in full, not broken down attribute by attribute. Read off `self.renderer.mapper`/
          `self.parser.mapper` (see `RendererBase.mapper`) — nothing a driver author declares by
          hand, and present separately for each side so the two can never silently drift apart
          unnoticed.
        - `"transport"`: `{"active": bool, "methods": [...]}` — which of
          `TransportBase.OPTIONAL_METHODS` (`execute`, `session`) is implemented.
        - `"observability"`: `{"active": bool, "methods": [...]}` — which of
          `ObservabilityBase.OPTIONAL_METHODS` (`get_lldp_neighbors`, `get_arp_table`,
          `get_routing_table`, `ping`, ...) is implemented.
        - `"normalizer"`: `{"active": bool}`.

        New optional methods are added once, on `ObservabilityBase`/`TransportBase` themselves —
        nothing here needs to change for them to be picked up. `render`/`parse`/`render_patch`
        themselves aren't reported here — a driver is assumed to implement those *if* it has the
        facade at all; what varies is *how much of the schema* it covers and *what else* it can
        do.

        `"active"` is an `isinstance` check against the matching base class, not just "is it set"
        — a facade that's some non-`None` object but doesn't actually follow the interface (e.g.
        a `parser_class` that forgot to subclass `ParserBase`) is honestly reported as inactive
        rather than crashing here or silently passing."""

        def _mapper_detail(active: bool, component: Any) -> dict[str, Any]:
            mapper = getattr(component, "mapper", None) if active else None
            return {"configuration": mapper.supported_components() if mapper is not None else []}

        def _hook_detail(active: bool, component: Any, base_cls: type) -> dict[str, Any]:
            methods = [m for m in base_cls.OPTIONAL_METHODS if active and _overrides_default(component, m, base_cls)]
            return {"methods": sorted(methods)}

        renderer_active = isinstance(self.renderer, RendererBase)
        parser_active = isinstance(self.parser, ParserBase)
        transport_active = isinstance(self.transport, TransportBase)
        observability_active = isinstance(self.observability, ObservabilityBase)
        return {
            "renderer": {"active": renderer_active, **_mapper_detail(renderer_active, self.renderer)},
            "parser": {"active": parser_active, **_mapper_detail(parser_active, self.parser)},
            "transport": {"active": transport_active, **_hook_detail(transport_active, self.transport, TransportBase)},
            "observability": {
                "active": observability_active,
                **_hook_detail(observability_active, self.observability, ObservabilityBase),
            },
            "normalizer": {"active": isinstance(self.normalizer, BaseNormalizer)},
        }

    @abstractmethod
    def render(self, logical_node: Any, asset: Any = None) -> Any:
        """Render logical node to device configuration.

        Args:
            logical_node: Logical node containing configuration
            asset: Optional asset context

        Returns:
            Rendered configuration
        """
        if self.renderer is None:
            raise NotImplementedError(f"{type(self).__name__} has no renderer_class configured")
        return self.renderer.render(logical_node.model_dump(), asset)

    @abstractmethod
    def parse(self, configuration: str) -> Any:
        """Parse device configuration.

        Args:
            configuration: Raw device configuration

        Returns:
            Parsed configuration model
        """
        if self.parser is None:
            raise NotImplementedError(f"{type(self).__name__} has no parser_class configured")
        return self.parser.parse(configuration)

    def normalize(self, raw: str) -> str:
        """Strip non-intent data (timestamps, auto-generated certs, etc.).

        Returns the cleaned config string. If no normalizer is configured
        the input is returned unchanged.
        """
        if self.normalizer is None:
            return raw
        return self.normalizer.normalize(raw).config

    def mask(self, raw: str) -> str:
        """Replace secrets with <REDACTED>.

        Returns the masked config string. If no normalizer is configured
        the input is returned unchanged.
        """
        if self.normalizer is None:
            return raw
        return self.normalizer.mask(raw).config
