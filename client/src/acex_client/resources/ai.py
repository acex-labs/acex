from collections.abc import Iterator

from acex_devkit.models.ai_ops import (
    AiAnalysisRequest,
    AiAskRequest,
    AiModelsResponse,
    AiProvidersResponse,
)

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
    stream,
)


class Ai(Resource, ActionMixin):
    """AI assistant — `/ai_ops/ai/*` (SSE-streamed).

    The `Acex` facade probes `HEAD /ai_ops/ai/ask` at construction; if the
    backend does not have `ai_ops` mounted, `client.ai` is set to `None`
    rather than an `Ai` instance.
    """

    path = "/ai_ops/ai"
    response_model = None  # type: ignore
    list_model = None  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("HEAD", "ask")
    def ping(self) -> None: ...

    @stream("POST", "ask")
    def ask(self, payload: AiAskRequest) -> Iterator[str]: ...

    @stream("POST", "config_analysis")
    def analyze(self, payload: AiAnalysisRequest) -> Iterator[str]: ...

    def providers(self) -> AiProvidersResponse:
        """Configured AI providers enriched with health, models and chains."""
        data = self.rest.request("GET", "/ai_ops/providers")
        return AiProvidersResponse.model_validate(data)

    def models(self, provider: str, refresh: bool = False) -> AiModelsResponse:
        """Model list for one provider (cache-aware; refresh=True bypasses cache)."""
        data = self.rest.request("GET", "/ai_ops/models", params={"provider": provider, "refresh": refresh})
        return AiModelsResponse.model_validate(data)
