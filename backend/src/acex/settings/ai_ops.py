"""AI Operations: named providers + per-task failover chains.

- **AIProvider**: a named OpenAI-compatible endpoint (base_url + api_key).
  Multiple chain levels can reference the same provider.
- **AIChainLevel**: one level in a failover chain — (provider name, model).
- **chains**: mapping task name → ordered list of levels. Supported tasks are
  "chat" and "analysis"; "default" is the chain other tasks inherit from.

In the environment, providers and chains are keyed by name:

  ACEX_AI_PROVIDERS__GROQ__BASE_URL=https://api.groq.com/openai/v1
  ACEX_AI_PROVIDERS__GROQ__API_KEY=gsk_...
  ACEX_AI_PROVIDERS__LOCAL__STATIC_MODELS=qwen3:32b,llama3.3
  ACEX_AI_PROVIDERS__LOCAL__MODEL_META={"qwen3:32b": {"supports_tools": true}}
  ACEX_AI_CHAINS__DEFAULT=groq/moonshotai/Kimi-K3,local/qwen3:32b
  ACEX_AI_CHAINS__ANALYSIS=groq/deepseek-r1
  ACEX_AI_MCP_SERVER_URL=http://localhost:8000/mcp

AI Ops is on as soon as a provider is configured, and off when none is.
"""

from typing import Any

from acex.settings.base import Section
from pydantic import BaseModel, field_validator, model_validator

#: Tasks with dedicated chains. Any other task name inherits "default".
KNOWN_TASKS = ("chat", "analysis")


class AIModelMeta(BaseModel):
    """Metadata about a model — capabilities and cost.

    Sourced from the provider's /models response when available (several
    OpenAI-compatible providers expose extra fields), overridable per model
    via the provider's `model_meta` config.
    """

    supports_tools: bool | None = None  # function calling / tool use
    supports_vision: bool | None = None
    context_window: int | None = None
    # Cost per 1M tokens, in the provider's currency unit (as reported upstream)
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    currency: str | None = None  # e.g. "USD", "SEK"
    # Any additional provider-specific fields, passed through untouched
    extra: dict | None = None


class AIProvider(BaseModel):
    """A named OpenAI-compatible endpoint."""

    #: Taken from the provider's key in AIOpsSettings.providers when left out.
    name: str = ""
    base_url: str
    api_key: str
    # Used when the provider has no GET /models endpoint (e.g. some local servers).
    # Comma-separated or JSON in the environment.
    static_models: list[str] | None = None
    # Per-model metadata overrides: {"model-id": {"supports_tools": true, ...}}.
    # Wins over whatever the provider's /models endpoint reports.
    model_meta: dict[str, AIModelMeta] = {}

    @field_validator("static_models", mode="before")
    @classmethod
    def _split(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class AIChainLevel(BaseModel):
    """One level in a failover chain: a model served by a named provider."""

    provider: str
    model: str


def _parse_level(value: Any) -> Any:
    """'provider/model' -> {'provider': ..., 'model': ...}; anything else passes through."""
    if not isinstance(value, str):
        return value
    value = value.strip()
    if "/" not in value:
        raise ValueError(f"Invalid chain level '{value}' — expected format 'provider/model'")
    provider, model = value.split("/", 1)
    return {"provider": provider.strip(), "model": model.strip()}


class AIOpsSettings(Section, env_prefix="ACEX_AI_"):
    """Providers + per-task failover chains."""

    providers: dict[str, AIProvider] = {}
    #: Each chain is a list of levels, or "provider/model,provider/model".
    chains: dict[str, list[AIChainLevel]] = {}
    mcp_server_url: str | None = None

    @field_validator("chains", mode="before")
    @classmethod
    def _parse_chains(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {
            task: [_parse_level(lvl) for lvl in (levels.split(",") if isinstance(levels, str) else levels) if lvl]
            for task, levels in value.items()
        }

    @model_validator(mode="after")
    def _check(self) -> "AIOpsSettings":
        for key, provider in self.providers.items():
            if not provider.name:
                provider.name = key
        if not self.providers:
            return self
        if not self.chains.get("default"):
            raise ValueError(
                "AI Ops has providers but no default chain. Set ACEX_AI_CHAINS__DEFAULT "
                "(e.g. groq/some-model) or pass chains={'default': [...]} (see docs/examples/ai_ops.md)."
            )
        for task, levels in self.chains.items():
            for level in levels:
                if level.provider not in self.providers:
                    raise ValueError(f"Chain '{task}' references unknown provider '{level.provider}'")
        return self

    @property
    def enabled(self) -> bool:
        return bool(self.providers)

    def chain_for(self, task: str) -> list[AIChainLevel]:
        """Return the failover chain for a task, inheriting from 'default'."""
        chain = self.chains.get(task) or self.chains.get("default")
        if not chain:
            raise ValueError(f"No AI chain configured for task '{task}' (and no 'default' chain)")
        return chain

    def provider_for(self, level: AIChainLevel) -> AIProvider:
        provider = self.providers.get(level.provider)
        if provider is None:
            raise ValueError(f"Chain level references unknown provider '{level.provider}'")
        return provider
