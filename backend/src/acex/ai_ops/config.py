"""
Configuration model for AI Operations: named providers + per-task failover chains.

Configurable via env vars (ACEX_AI_*) or programmatically via
`AutomationEngine.ai_ops(...)` — code wins over env, same pattern as
`InfluxDBSettings`.

Concepts
--------
- **AIProvider**: a named OpenAI-compatible endpoint (base_url + api_key).
  Multiple chain levels can reference the same provider.
- **AIChainLevel**: one level in a failover chain — (provider name, model).
- **chains**: mapping task name → ordered list of levels. Supported tasks are
  "chat" and "analysis"; "default" is the chain other tasks inherit from.

Env var layout (code overrides env)
-------------------------------------
Providers:
  ACEX_AI_PROVIDERS=groq,local
  ACEX_AI_PROVIDER_GROQ_BASEURL=https://api.groq.com/openai/v1
  ACEX_AI_PROVIDER_GROQ_API_KEY=gsk_...
  ACEX_AI_PROVIDER_GROQ_STATIC_MODELS=model-a,model-b   (optional)
  ACEX_AI_PROVIDER_LOCAL_BASEURL=...
  ACEX_AI_PROVIDER_LOCAL_MODEL_META={"qwen3:32b": {"supports_tools": true}}  (optional JSON)

Chains (comma-separated provider/model levels, in failover order):
  ACEX_AI_CHAIN_DEFAULT=groq/moonshotai/Kimi-K3,local/qwen3:32b
  ACEX_AI_CHAIN_ANALYSIS=groq/deepseek-r1

MCP tool server:
  ACEX_AI_MCP_SERVER_URL=http://localhost:8000/mcp
"""

import json
import os

from pydantic import BaseModel

ENV_PREFIX = "ACEX_AI_"

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

    name: str
    base_url: str
    api_key: str
    # Used when the provider has no GET /models endpoint (e.g. some local servers)
    static_models: list[str] | None = None
    # Per-model metadata overrides: {"model-id": {"supports_tools": true, ...}}.
    # Wins over whatever the provider's /models endpoint reports.
    model_meta: dict[str, "AIModelMeta"] = {}


class AIChainLevel(BaseModel):
    """One level in a failover chain: a model served by a named provider."""

    provider: str
    model: str


class AIOpsSettings(BaseModel):
    """Providers + per-task failover chains."""

    providers: dict[str, AIProvider]
    chains: dict[str, list[AIChainLevel]]
    mcp_server_url: str | None = None

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

    # ------------------------------------------------------------------
    # Env parsing
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "AIOpsSettings | None":
        """Build settings from ACEX_AI_* env vars. None if nothing configured."""
        providers = cls._providers_from_env()
        if not providers:
            return None
        chains = cls._chains_from_env(providers)
        if not chains:
            return None
        return cls(
            providers=providers,
            chains=chains,
            mcp_server_url=os.environ.get(f"{ENV_PREFIX}MCP_SERVER_URL"),
        )

    @staticmethod
    def _providers_from_env() -> dict[str, "AIProvider"]:
        providers: dict[str, AIProvider] = {}

        # Named providers: ACEX_AI_PROVIDERS=groq,local,...
        names = os.environ.get(f"{ENV_PREFIX}PROVIDERS", "")
        for name in [n.strip() for n in names.split(",") if n.strip()]:
            prefix = f"{ENV_PREFIX}PROVIDER_{name.upper()}_"
            p_base = os.environ.get(f"{prefix}BASEURL")
            p_key = os.environ.get(f"{prefix}API_KEY")
            if not (p_base and p_key):
                continue
            static = os.environ.get(f"{prefix}STATIC_MODELS")
            meta_raw = os.environ.get(f"{prefix}MODEL_META")
            providers[name] = AIProvider(
                name=name,
                base_url=p_base,
                api_key=p_key,
                static_models=[m.strip() for m in static.split(",")] if static else None,
                model_meta=json.loads(meta_raw) if meta_raw else {},
            )
        return providers

    @staticmethod
    def _chains_from_env(providers: dict[str, "AIProvider"]) -> dict[str, list[AIChainLevel]]:
        def parse_chain(value: str) -> list[AIChainLevel]:
            levels = []
            for item in value.split(","):
                item = item.strip()
                if not item:
                    continue
                if "/" not in item:
                    raise ValueError(f"Invalid chain level '{item}' — expected format 'provider/model'")
                provider, model = item.split("/", 1)
                levels.append(AIChainLevel(provider=provider.strip(), model=model.strip()))
            return levels

        chains: dict[str, list[AIChainLevel]] = {}
        for task in ("default", *KNOWN_TASKS):
            raw = os.environ.get(f"{ENV_PREFIX}CHAIN_{task.upper()}")
            if raw:
                chains[task] = parse_chain(raw)

        # Validate provider references
        for task, levels in chains.items():
            for level in levels:
                if level.provider not in providers:
                    raise ValueError(f"Chain '{task}' references unknown provider '{level.provider}'")
        return chains
