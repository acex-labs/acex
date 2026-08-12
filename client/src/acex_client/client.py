"""Acex — synchronous Python client for the ACE-X backend.

Usage:
    from acex_client import Acex

    with Acex(base_url="https://acex.local") as client:
        node = client.inventory.node_instances.get(1)
        print(node.hostname)

Namespaces:
    client.inventory         — sites, regions, contacts, assets, asset_clusters,
                                collection_agents, credentials, logical_nodes,
                                management_connections, node_instances,
                                region_assignments, contact_assignments
    client.observability     — agents (with bound outputs/rules/nodes), grafana
    client.operations        — compliance, config_history, lldp
    client.config_components — catalog, generate, reconcile, translate, drivers
    client.neds              — list, get, download
    client.ai                — ask, analyze (SSE-streamed) or None if backend
                              does not mount ai_ops
    client.system            — auth_config, health_node, health_site
"""

from __future__ import annotations

from acex_client.auth import AuthProvider, create_auth_provider
from acex_client.http import RestClient
from acex_client.resources.ai import Ai
from acex_client.resources.config_components import ConfigComponents
from acex_client.resources.inventory import InventoryNamespace
from acex_client.resources.neds import Neds
from acex_client.resources.observability import ObservabilityNamespace
from acex_client.resources.operations import OperationsNamespace
from acex_client.resources.system import SystemNamespace


class Acex:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1/",
        *,
        api_version: int = 1,
        verify: bool = True,
        auth: AuthProvider | None = None,
        timeout: float = 30.0,
    ):
        # Normalize base_url so concatenation with /api/v{ver} is safe.
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        self.api_url = f"{base_url}api/v{api_version}"
        self.verify = verify
        self.timeout = timeout

        resolved_auth = auth or create_auth_provider(self.api_url, verify)
        self.rest = RestClient(self.api_url, resolved_auth, verify=verify, timeout=timeout)

        # Build all namespaces eagerly. Resources are cheap to construct; the
        # expensive work (HTTP) happens only on method calls.
        self.inventory = InventoryNamespace(self.rest)
        self.observability = ObservabilityNamespace(self.rest)
        self.operations = OperationsNamespace(self.rest)
        self.config_components = ConfigComponents(self.rest)
        self.neds = Neds(self.rest)
        self.system = SystemNamespace(self.rest)

        # AI is optional — HEAD-probe /ai_ops/ai/ask/. If the backend doesn't
        # mount ai_ops, set self.ai to None so callers can `if client.ai:`.
        self.ai = self._probe_ai()

    def _probe_ai(self) -> Ai | None:
        """Return an Ai instance if /ai_ops/ai/ask/ responds, else None."""
        try:
            Ai(self.rest).ping()
            return Ai(self.rest)
        except Exception:
            return None

    def close(self) -> None:
        self.rest.close()

    def __enter__(self) -> Acex:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @classmethod
    def from_env(cls, base_url: str | None = None, **kwargs) -> Acex:
        """Construct an Acex client auto-configuring auth from environment.

        `base_url` defaults to the ACEX_BASE_URL env var. Other auth env vars
        (ACEX_ISSUER_URL, ACEX_CLIENT_ID, ACEX_CLIENT_SECRET, ACEX_VERIFY_SSL)
        are read by `create_auth_provider`. Pass kwargs to override the
        Acex constructor defaults.
        """
        import os

        url = base_url or os.environ.get("ACEX_BASE_URL", "http://127.0.0.1/")
        return cls(base_url=url, **kwargs)


__all__ = ["Acex"]
