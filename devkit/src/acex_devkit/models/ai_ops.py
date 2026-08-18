from pydantic import BaseModel


class AiAskRequest(BaseModel):
    """Body for `POST /ai_ops/ai/ask/`. Returns an SSE stream of str chunks."""

    question: str
    node_instance_id: int | None = None
    site: str | None = None
    # Explicit model override ("provider/model" or "model"). Omitted = failover chain.
    model: str | None = None


class AiAnalysisTask(BaseModel):
    """Task type for AI config-diff analysis."""

    name: str
    description: str = ""


class AiAnalysisRequest(BaseModel):
    """Body for `POST /ai_ops/ai/config_analysis/`. Returns an SSE stream."""

    task: str  # "explain" | "risk_assessment" | "alignment"
    diff: str
    node_instance_id: int | None = None
    model: str | None = None


class AiChainLevel(BaseModel):
    """One level in a failover chain, as exposed by `GET /ai_ops/providers`."""

    provider: str
    model: str


class AiModelInfo(BaseModel):
    """One available model with capability/cost metadata.

    Fields are None when the provider does not report them and no
    override is configured.
    """

    id: str
    is_chat_model: bool = True  # False for embeddings/STT/rerank/image models
    supports_tools: bool | None = None  # function calling / tool use
    supports_vision: bool | None = None
    context_window: int | None = None
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    currency: str | None = None
    extra: dict | None = None  # provider-specific passthrough


class AiProviderInfo(BaseModel):
    """A configured AI provider enriched with health + available models."""

    name: str
    base_url: str
    status: str  # "ok" | "unreachable"
    models: list[AiModelInfo] = []
    has_static_models: bool = False


class AiProvidersResponse(BaseModel):
    """Response for `GET /ai_ops/providers`."""

    providers: list[AiProviderInfo]
    # Per-task failover chains: task name -> ordered levels. Tasks not
    # explicitly configured inherit "default".
    chains: dict[str, list[AiChainLevel]] = {}


class AiModelsResponse(BaseModel):
    """Response for `GET /ai_ops/models?provider=X`."""

    provider: str
    models: list[AiModelInfo]
