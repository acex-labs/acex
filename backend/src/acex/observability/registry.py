import inspect
from collections.abc import Iterable
from dataclasses import dataclass, field

from acex.observability.capability import TelemetryCapability
from acex.observability.components.base import TelemetryComponent
from acex.observability.providers import (
    Provider,
    ProviderResult,
    icmp_ping_provider,
    snmp_provider,
)
from acex_devkit.models.telemetry_agent import CapabilityCoverage

# Reason used when a node-scoped capability produced neither a component nor
# an explicit skip for a node (e.g. a custom provider that ignores it).
NOT_PRODUCED = "not_produced"


@dataclass
class _RegisteredProvider:
    fn: Provider
    # Capability this provider's components belong to. None = unknown
    # (legacy/custom providers) — always invoked, filtered per component.
    capability: TelemetryCapability | None = None


@dataclass(frozen=True)
class SkippedCapability:
    node_id: int
    capability: TelemetryCapability | None
    reason: str
    detail: str | None = None


@dataclass
class AgentComponents:
    components: list[TelemetryComponent] = field(default_factory=list)
    skipped: list[SkippedCapability] = field(default_factory=list)
    # Granted capabilities that render per node (e.g. icmp, snmp).
    node_capabilities: list[TelemetryCapability] = field(default_factory=list)

    def coverage(self, node_ids: Iterable[int]) -> dict[int, dict[TelemetryCapability, CapabilityCoverage]]:
        """Per node, per node-scoped capability: rendered, or skipped with reason."""
        rendered = {(c.target_node(), c.capability) for c in self.components if c.target_node() is not None}
        skipped = {(s.node_id, s.capability): s for s in self.skipped}

        out: dict[int, dict[TelemetryCapability, CapabilityCoverage]] = {}
        for node_id in node_ids:
            caps: dict[TelemetryCapability, CapabilityCoverage] = {}
            for cap in self.node_capabilities:
                if (node_id, cap) in rendered:
                    caps[cap] = CapabilityCoverage(status="rendered")
                elif s := skipped.get((node_id, cap)):
                    caps[cap] = CapabilityCoverage(status="skipped", reason=s.reason, detail=s.detail)
                else:
                    caps[cap] = CapabilityCoverage(status="skipped", reason=NOT_PRODUCED)
            out[node_id] = caps
        return out


class TelemetryRegistry:
    """
    Builds the live set of TelemetryComponents from current ACEX state.

    The registry is *not* persisted — it is reconstructed on demand from
    inventory and config. This keeps it consistent with declared intent
    and avoids a stale source of truth.

    Providers are functions that inspect ACEX state (DB, inventory, config)
    and yield TelemetryComponents. Defaults are wired in __init__; integrators
    can extend via `register_provider`.
    """

    def __init__(self, db_manager, credential_manager=None):
        self.db = db_manager
        self.credential_manager = credential_manager
        self._providers: list[_RegisteredProvider] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_provider(icmp_ping_provider, capability=TelemetryCapability.icmp)
        self.register_provider(snmp_provider, capability=TelemetryCapability.snmp)

    def register_provider(self, provider: Provider, capability: TelemetryCapability | None = None) -> None:
        """Register a provider.

        Passing `capability` lets agent-scoped rendering skip the provider
        entirely when an agent does not grant it. Providers may accept
        `node_ids` and/or `credential_manager` keyword args, and may return
        a ProviderResult or a plain list of components.
        """
        self._providers.append(_RegisteredProvider(provider, capability))

    def _call_provider(self, entry: _RegisteredProvider, node_ids: set[int] | None) -> ProviderResult:
        params = inspect.signature(entry.fn).parameters
        kwargs = {}
        if "credential_manager" in params:
            kwargs["credential_manager"] = self.credential_manager
        if "node_ids" in params:
            kwargs["node_ids"] = node_ids
        result = entry.fn(self.db, **kwargs)
        if isinstance(result, ProviderResult):
            return result
        return ProviderResult(components=list(result))

    def build(self) -> list[TelemetryComponent]:
        components: list[TelemetryComponent] = []
        for entry in self._providers:
            components.extend(self._call_provider(entry, None).components)
        return components

    def by_kind(self, kind: str) -> list[TelemetryComponent]:
        return [c for c in self.build() if c.kind == kind]

    def for_telegraf_agent(
        self,
        node_ids: Iterable[int],
        capabilities: Iterable[TelemetryCapability],
    ) -> AgentComponents:
        """
        Components a given TelemetryAgent should collect: gated by the
        agent's granted capabilities and scoped to its assigned/matched nodes.

        Providers whose capability is not granted are not invoked. Nodes a
        provider could not render are returned in `skipped`, tagged with the
        provider's capability; `AgentComponents.coverage()` turns this into
        a per-node, per-capability view.

        Components without a `capability` are excluded from agent-scoped
        rendering — they belong to other delivery paths. Components without
        a `target_node` (cross-node aggregates) are included whenever their
        capability is granted.
        """
        node_set = set(node_ids)
        cap_set = set(capabilities)
        out = AgentComponents()
        node_caps: set[TelemetryCapability] = set()

        for entry in self._providers:
            if entry.capability is not None and entry.capability not in cap_set:
                continue
            if entry.capability is not None:
                node_caps.add(entry.capability)
            result = self._call_provider(entry, node_set)

            for c in result.components:
                if c.capability is None or c.capability not in cap_set:
                    continue
                tn: int | None = c.target_node()
                if tn is not None and tn not in node_set:
                    continue
                if tn is not None:
                    node_caps.add(c.capability)
                out.components.append(c)

            for s in result.skipped:
                if s.node_id in node_set:
                    out.skipped.append(SkippedCapability(s.node_id, entry.capability, s.reason, s.detail))

        # Keep the agent's own capability order for stable output.
        out.node_capabilities = [c for c in capabilities if c in node_caps]
        return out
