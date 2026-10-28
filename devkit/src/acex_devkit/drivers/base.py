"""The NED interface: what a network element driver implements and what callers use.

A NED is an adapter for one device type. Callers only see `NetworkElementDriver` and the
`Session` it opens; the facades below are what a driver author writes:

- `Codec`     configuration syntax in both directions, no device, independent of transport
- `Transport` talks to the device (CLI, NETCONF, REST, ...), one instance per session
- `State`     reads operational state into devkit models, opt-in per method
- `Actions`   runs actions such as ping, opt-in per method

Codec and transport share a payload type: the payload `Codec.render` and `Codec.render_patch`
return is what `Transport.apply` sends, e.g. `Codec[str]` with `Transport[str]` for CLI text.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar, get_args, get_origin, get_type_hints

from pydantic import TypeAdapter

from acex_devkit.configdiffer import Diff
from acex_devkit.exceptions import DriverException
from acex_devkit.models.actions import PingParams, PingResult
from acex_devkit.models.asset import Asset
from acex_devkit.models.codec_result import ParseResult, RenderResult
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_devkit.models.credential import CredentialSecret
from acex_devkit.models.lldp_neighbor import LldpNeighborEntry
from acex_devkit.models.management_connection import ConnectionType
from acex_devkit.models.ned import Capabilities, Platform
from acex_devkit.models.node_response import NodeInstance
from acex_devkit.models.state import ArpEntry, DeviceFacts, StateKind


class Facade:
    """Detects which optional methods a facade implements, so capabilities are never declared by hand."""

    validate_results: ClassVar[bool] = False  # check results against the base class's declared return type

    @staticmethod
    def optional(method):
        method.__acex_optional__ = True
        return method

    @classmethod
    def implemented(cls) -> list[str]:
        names = {name for c in cls.__mro__ for name, v in vars(c).items() if getattr(v, "__acex_optional__", False)}
        return sorted(name for name in names if not getattr(getattr(cls, name), "__acex_optional__", False))

    @classmethod
    def payload_type(cls) -> Any:
        """The `Payload` a codec or transport is parametrized with, or None when left generic."""
        for base in cls.__mro__:
            for orig in getattr(base, "__orig_bases__", ()):
                if get_origin(orig) in (Codec, Transport) and not isinstance(arg := get_args(orig)[0], TypeVar):
                    return arg
        return None

    def require(self, method: str) -> None:
        if method not in self.implemented():
            raise DriverException(f"{type(self).__name__} does not implement {method}")

    def check(self, method: str, result: Any) -> Any:
        if not self.validate_results:
            return result
        # Validate against the return type the base class declares, not the driver's override.
        base = next(c for c in type(self).__mro__ if getattr(vars(c).get(method), "__acex_optional__", False))
        return TypeAdapter(get_type_hints(vars(base)[method])["return"]).validate_python(result)


class Codec[Payload](Facade, ABC):
    """Configuration syntax in both directions. Pure: no device, no transport."""

    mapper: Any = None  # a devkit Mapper; its components are reported as capabilities

    @abstractmethod
    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult[Payload]:
        """Full configuration; its `payload` is sendable with `Transport.apply`."""

    @abstractmethod
    def parse(self, raw: Any, node: NodeInstance) -> ParseResult: ...

    @abstractmethod
    def render_patch(self, diff: Diff, node: NodeInstance) -> RenderResult[Payload]:
        """Every change in `diff`, removals included; its `payload` is sendable with `Transport.apply`. The
        caller decides what the diff holds (`Diff.scoped`); the trees it was made from are on it. A change the
        syntax can't express is left out and listed in `metadata.unrendered`."""

    @abstractmethod
    def mask(self, raw: Any) -> Any:
        """Replace secrets. Must be idempotent: mask(mask(x)) == mask(x)."""

    def normalize(self, raw: Any) -> Any:
        return raw


class Transport[Payload](Facade, ABC):
    """Talks to one device. Created per session; the only part holding device state.

    `node` is None when the session was opened against a raw address, e.g. for discovery.
    """

    connection_types: ClassVar[set[ConnectionType] | None] = None  # management connections it can use; None = any

    def __init__(self, address: str, credentials: list[CredentialSecret], node: NodeInstance | None = None):
        self.address = address
        self.credentials = credentials
        self.node = node

    def credential(self, credential_type: str, required: bool = True) -> CredentialSecret | None:
        credential = next((c for c in self.credentials if c.credential_type == credential_type), None)
        if credential is None and required:
            raise DriverException(f"{self.address} has no {credential_type} credential")
        return credential

    @abstractmethod
    async def open(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @Facade.optional
    async def get_config(self) -> Any:
        raise NotImplementedError

    @Facade.optional
    async def apply(self, payload: Payload) -> Any:
        """Send what `Codec.render` or `Codec.render_patch` returned."""
        raise NotImplementedError

    @Facade.optional
    async def execute(self, request: Any) -> Any:
        raise NotImplementedError


class State(Facade):
    """Operational state. Implement `get_<kind>` for each supported StateKind."""

    validate_results = True

    @classmethod
    def kinds(cls) -> list[StateKind]:
        return [StateKind(name.removeprefix("get_")) for name in cls.implemented()]

    @Facade.optional
    async def get_facts(self, transport: Transport) -> DeviceFacts:
        raise NotImplementedError

    @Facade.optional
    async def get_lldp_neighbors(self, transport: Transport) -> list[LldpNeighborEntry]:
        raise NotImplementedError

    @Facade.optional
    async def get_arp_table(self, transport: Transport) -> list[ArpEntry]:
        raise NotImplementedError


class Actions(Facade):
    """Actions run from the device. Implement one method per action."""

    validate_results = True

    @Facade.optional
    async def ping(self, transport: Transport, params: PingParams) -> PingResult:
        raise NotImplementedError


class Session:
    """One connection to one device. Calls run one at a time, in the order they are made."""

    def __init__(self, transport: Transport, state: State | None, actions: Actions | None):
        self.transport = transport
        self.state = state
        self.actions = actions
        self.lock = asyncio.Lock()

    async def __aenter__(self) -> "Session":
        await self.transport.open()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.transport.close()

    async def get_config(self) -> Any:
        """Raw and unmasked."""
        return await self.call(self.transport, "get_config")

    async def apply(self, payload: Any) -> Any:
        return await self.call(self.transport, "apply", payload)

    async def execute(self, request: Any) -> Any:
        """Raw, vendor-specific and unmasked."""
        return await self.call(self.transport, "execute", request)

    async def get_facts(self) -> DeviceFacts:
        return await self.call(self.state, "get_facts", self.transport)

    async def get_lldp_neighbors(self) -> list[LldpNeighborEntry]:
        return await self.call(self.state, "get_lldp_neighbors", self.transport)

    async def get_arp_table(self) -> list[ArpEntry]:
        return await self.call(self.state, "get_arp_table", self.transport)

    async def ping(self, params: PingParams) -> PingResult:
        return await self.call(self.actions, "ping", self.transport, params)

    async def call(self, facade: Facade | None, method: str, *args) -> Any:
        if facade is None:
            raise DriverException(f"Driver does not support {method}")
        facade.require(method)
        async with self.lock:
            result = await getattr(facade, method)(*args)
        return facade.check(method, result)


class NetworkElementDriver:
    """Base class for network element drivers.

    A driver declares its facades and the platforms it supports. Everything else,
    including which functions it implements, comes from this class.
    """

    codec_class: ClassVar[type[Codec] | None] = None
    transport_class: ClassVar[type[Transport] | None] = None
    state_class: ClassVar[type[State] | None] = None
    actions_class: ClassVar[type[Actions] | None] = None

    platforms: ClassVar[list[Platform]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.codec_class is None or cls.transport_class is None:
            return
        codec, transport = cls.codec_class.payload_type(), cls.transport_class.payload_type()
        if codec is not None and transport is not None and codec != transport:
            raise TypeError(
                f"{cls.__name__}: {cls.codec_class.__name__} renders {codec}, "
                f"but {cls.transport_class.__name__} applies {transport}"
            )

    def __init__(self):
        self.codec = self.codec_class() if self.codec_class else None
        self.state = self.state_class() if self.state_class else None
        self.actions = self.actions_class() if self.actions_class else None

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            platforms=self.platforms,
            configuration=self.codec.mapper.supported_components() if self.codec and self.codec.mapper else [],
            operations=self.transport_class.implemented() if self.transport_class else [],
            state=self.state_class.kinds() if self.state_class else [],
            actions=self.actions_class.implemented() if self.actions_class else [],
        )

    def supports(self, asset: Asset) -> bool:
        return any(platform.matches(asset) for platform in self.platforms)

    def render(self, config: ComposedConfiguration, node: NodeInstance) -> RenderResult:
        return self.require_codec().render(config, node)

    def parse(self, raw: Any, node: NodeInstance) -> ParseResult:
        return self.require_codec().parse(raw, node)

    def render_patch(self, diff: Diff, node: NodeInstance) -> RenderResult:
        return self.require_codec().render_patch(diff, node)

    def normalize(self, raw: Any) -> Any:
        return self.require_codec().normalize(raw)

    def mask(self, raw: Any) -> Any:
        return self.require_codec().mask(raw)

    def session(self, node: NodeInstance, credentials: list[CredentialSecret]) -> Session:
        """A session to a node instance, at the management connection its transport can use.

        Among the connections of a type the transport handles, the primary one wins, otherwise the oldest.
        """
        types = self.require_transport().connection_types
        usable = [
            c for c in node.management_connections if c.target_ip and (types is None or c.connection_type in types)
        ]
        if not usable:
            kinds = ", ".join(sorted(types)) if types else "any"
            raise DriverException(f"{node.logical_node.hostname} has no management connection of type {kinds}")
        connection = min(usable, key=lambda c: (not c.primary, c.id))
        return self.connect(connection.target_ip, credentials, node)

    def connect(self, address: str, credentials: list[CredentialSecret], node: NodeInstance | None = None) -> Session:
        """A session to an explicit address, e.g. a raw asset during discovery.

        With a node instance its platform is checked; without one, e.g. before the node exists, it is not.
        """
        transport_class = self.require_transport()
        if node is not None:
            assets = node.asset.assets if node.asset.type == "asset_cluster" else [node.asset]
            unsupported = [
                f"{a.os} {a.hardware_model} {a.os_version or ''}".strip() for a in assets if not self.supports(a)
            ]
            if unsupported:
                raise DriverException(f"{type(self).__name__} does not support {', '.join(unsupported)}")
        return Session(transport_class(address, credentials, node), self.state, self.actions)

    def require_transport(self) -> type[Transport]:
        if self.transport_class is None:
            raise DriverException(f"{type(self).__name__} has no transport")
        return self.transport_class

    def require_codec(self) -> Codec:
        if self.codec is None:
            raise DriverException(f"{type(self).__name__} has no codec")
        return self.codec
