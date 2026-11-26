"""Connections to providers: one credential per provider, one adapter per URL."""

from collections.abc import Awaitable, Callable

from .adapters import ADAPTERS, ModelAdapter
from .auth import AzureClientSecretToken
from .config import AIOpsSettings, AIProvider


class Endpoints:
    """Builds adapters lazily and keeps them for the life of the process.

    Adapters are keyed by URL and protocol rather than by provider: a provider
    whose models each have their own base_url needs one client per model.
    The credential is per provider, so those clients share one token cache.
    """

    def __init__(self, settings: AIOpsSettings):
        self.settings = settings
        self._credentials: dict[str, str | Callable[[], Awaitable[str]]] = {}
        self._adapters: dict[tuple[str, str, str], ModelAdapter] = {}

    def adapter(self, provider: AIProvider, model_id: str) -> ModelAdapter:
        """The adapter that serves one model."""
        base_url, api = provider.endpoint(model_id)
        return self._adapter(provider, base_url, api)

    def listing_adapter(self, provider: AIProvider) -> ModelAdapter:
        """The adapter for the provider's own base_url, which lists its models."""
        return self._adapter(provider, provider.base_url, provider.api)

    def _adapter(self, provider: AIProvider, base_url: str, api: str) -> ModelAdapter:
        key = (provider.name, api, base_url)
        adapter = self._adapters.get(key)
        if adapter is None:
            adapter = self._adapters[key] = ADAPTERS[api](base_url, self._credential(provider))
        return adapter

    def _credential(self, provider: AIProvider) -> str | Callable[[], Awaitable[str]]:
        credential = self._credentials.get(provider.name)
        if credential is None:
            credential = AzureClientSecretToken(provider.auth) if provider.auth else provider.api_key
            self._credentials[provider.name] = credential
        return credential
