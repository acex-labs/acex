from typing import Callable, Iterable, List, Optional

from acex.observability.capability import TelemetryCapability
from acex.observability.components.base import TelemetryComponent
from acex.observability.providers import icmp_ping_provider


Provider = Callable[["object"], List[TelemetryComponent]]


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

    def __init__(self, db_manager):
        self.db = db_manager
        self._providers: List[Provider] = []
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._providers.append(icmp_ping_provider)

    def register_provider(self, provider: Provider) -> None:
        self._providers.append(provider)

    def build(self) -> List[TelemetryComponent]:
        components: List[TelemetryComponent] = []
        for provider in self._providers:
            components.extend(provider(self.db))
        return components

    def by_kind(self, kind: str) -> List[TelemetryComponent]:
        return [c for c in self.build() if c.kind == kind]

    def for_telegraf_agent(
        self,
        node_ids: Iterable[int],
        capabilities: Iterable[TelemetryCapability],
    ) -> List[TelemetryComponent]:
        """
        Components a given TelemetryAgent should collect: gated by the
        agent's granted capabilities and scoped to its assigned/matched nodes.

        Components without a `capability` (none currently) are excluded
        from agent-scoped rendering — they belong to other delivery paths.
        Components without a `target_node` (cross-node aggregates) are
        included whenever their capability is granted.
        """
        node_set = set(node_ids)
        cap_set = set(capabilities)
        out: List[TelemetryComponent] = []
        for c in self.build():
            if c.capability is None or c.capability not in cap_set:
                continue
            tn: Optional[int] = c.target_node()
            if tn is not None and tn not in node_set:
                continue
            out.append(c)
        return out
