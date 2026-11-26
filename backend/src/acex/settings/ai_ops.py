"""AI Operations: named providers, their models, and per-task failover chains.

- **AIProvider**: a named endpoint — where it is (base_url), how to sign in
  (api_key or auth) and which wire protocol it speaks (api). Its models share
  all three unless a model overrides them.
- **AIModelConfig**: one model of a provider — call settings (reasoning effort,
  extra request params, its own base_url or api) and what it can do (tools,
  vision, context window, cost). Anything left out is taken from the
  provider's /models listing when it has one.
- **AIChainLevel**: one level in a failover chain — (provider, model), plus
  call settings that apply to that task only.
- **chains**: task name → ordered list of levels. Supported tasks are "chat"
  and "analysis"; "default" is the chain other tasks inherit from.

In the environment, providers and chains are keyed by name:

  ACEX_AI_OPS_PROVIDERS__GROQ__BASE_URL=https://api.groq.com/openai/v1
  ACEX_AI_OPS_PROVIDERS__GROQ__API_KEY=gsk_...
  ACEX_AI_OPS_PROVIDERS__LOCAL__MODELS=qwen3:32b,llama3.3
  ACEX_AI_OPS_PROVIDERS__AZURE__BASE_URL=https://apim.example.com/{model}/openai/v1/
  ACEX_AI_OPS_PROVIDERS__AZURE__API=responses
  ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__TYPE=azure_client_secret   # instead of API_KEY
  ACEX_AI_OPS_PROVIDERS__AZURE__AUTH__TENANT_ID=...              # + CLIENT_ID, CLIENT_SECRET, SCOPE
  ACEX_AI_OPS_PROVIDERS__AZURE__MODELS={"gpt-6.1": {"reasoning_effort": "medium"}}
  ACEX_AI_OPS_CHAINS__DEFAULT=groq/moonshotai/Kimi-K3,local/qwen3:32b
  ACEX_AI_OPS_CHAINS__ANALYSIS=[{"provider": "azure", "model": "gpt-6.1", "reasoning_effort": "high"}]
  ACEX_AI_OPS_MCP_SERVER_URL=http://localhost:8000/mcp

AI Ops is on as soon as a provider is configured, and off when none is.
"""

import json
from typing import Any, Literal

from acex.settings.section import Section
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

#: Tasks with dedicated chains. Any other task name inherits "default".
KNOWN_TASKS = ("chat", "analysis")

#: Wire protocols. chat_completions is what OpenAI-compatible servers speak;
#: responses is OpenAI's newer API, the only one on which OpenAI and Azure
#: reasoning models accept tools.
AIApi = Literal["chat_completions", "responses"]

#: Placeholder in a base_url that is replaced by the model id, for gateways
#: that give each model its own URL.
MODEL_PLACEHOLDER = "{model}"


class _Strict(BaseModel):
    """Rejects unknown fields, so a misspelt or renamed setting fails at startup
    instead of being ignored — as Section does for the top level."""

    model_config = ConfigDict(extra="forbid")


class AIModelConfig(_Strict):
    """One model of a provider: how to call it and what it can do.

    Capability and cost fields left as None are taken from the provider's
    /models listing; what is set here wins over that listing.
    """

    #: Overrides the provider's base_url for this model.
    base_url: str | None = None
    #: Overrides the provider's api for this model.
    api: AIApi | None = None
    #: "none", "low", "medium", "high", ... — sent as the protocol expects it.
    reasoning_effort: str | None = None
    #: Extra request fields sent as they are, e.g. {"temperature": 0.2}.
    params: dict[str, Any] = {}

    supports_tools: bool | None = None  # function calling / tool use
    supports_vision: bool | None = None
    context_window: int | None = None
    # Cost per 1M tokens, in the provider's currency unit (as reported upstream)
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    currency: str | None = None  # e.g. "USD", "SEK"
    # Any additional provider-specific fields, passed through untouched
    extra: dict | None = None


class AzureClientSecretAuth(_Strict):
    """Entra ID client credentials, for an endpoint that takes a fresh Entra token
    as its bearer instead of a static key (e.g. Azure OpenAI behind API Management).

    Tokens come from azure.identity.ClientSecretCredential, which caches them and
    renews them before they expire.
    """

    type: Literal["azure_client_secret"]
    tenant_id: str
    client_id: str
    client_secret: str
    #: Scope the token is requested for, e.g. https://cognitiveservices.azure.com/.default
    scope: str


class AIProvider(_Strict):
    """A named endpoint, authenticated by `api_key` or `auth`."""

    #: Taken from the provider's key in AIOpsSettings.providers when left out.
    name: str = ""
    #: May contain {model} when every model has its own URL.
    base_url: str
    api: AIApi = "chat_completions"
    api_key: str | None = None
    auth: AzureClientSecretAuth | None = None
    #: Models configured by hand: {"model-id": {...}}. In the environment also
    #: "a,b" or a JSON list when they need no settings. They are listed even when
    #: the provider's /models does not report them, which is how a provider
    #: without /models gets a model list at all. Always a dict once validated;
    #: the list in the type is what lets the environment give "a,b" at all.
    models: dict[str, AIModelConfig] | list[str] = {}

    @field_validator("models", mode="before")
    @classmethod
    def _model_list(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip().startswith("{"):
            value = json.loads(value) if value.strip().startswith("[") else value.split(",")
        if isinstance(value, list):
            return {item.strip(): {} for item in value if item.strip()}
        return value

    @model_validator(mode="after")
    def _check(self) -> "AIProvider":
        if (self.api_key is None) == (self.auth is None):
            raise ValueError("An AI provider needs exactly one of api_key or auth")
        if not self.discoverable and not self.models:
            raise ValueError(
                f"AI provider base_url '{self.base_url}' has a {MODEL_PLACEHOLDER} placeholder, so it has no "
                "/models to list; configure its models"
            )
        return self

    @property
    def discoverable(self) -> bool:
        """Whether the provider has one /models endpoint to list models from."""
        return MODEL_PLACEHOLDER not in self.base_url

    def model(self, model_id: str) -> AIModelConfig:
        return self.models.get(model_id) or AIModelConfig()

    def endpoint(self, model_id: str) -> tuple[str, AIApi]:
        """(base_url, api) that serve a model."""
        config = self.model(model_id)
        return (config.base_url or self.base_url).replace(MODEL_PLACEHOLDER, model_id), config.api or self.api


class AIChainLevel(_Strict):
    """One level in a failover chain: a model served by a named provider, with
    call settings for this task that win over the model's own."""

    provider: str
    model: str
    reasoning_effort: str | None = None
    params: dict[str, Any] = {}

    @classmethod
    def parse(cls, value: Any) -> Any:
        """'provider/model' -> {'provider': ..., 'model': ...}; anything else passes through."""
        if not isinstance(value, str):
            return value
        value = value.strip()
        if "/" not in value:
            raise ValueError(f"Invalid chain level '{value}' — expected format 'provider/model'")
        provider, model = value.split("/", 1)
        return {"provider": provider.strip(), "model": model.strip()}

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}"


class AIOpsSettings(Section, name="ai_ops"):
    """Providers + per-task failover chains."""

    providers: dict[str, AIProvider] = {}
    #: Each chain is a list of levels, "provider/model,provider/model", or a JSON list.
    chains: dict[str, list[AIChainLevel]] = {}
    mcp_server_url: str | None = None

    @field_validator("chains", mode="before")
    @classmethod
    def _parse_chains(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        parsed = {}
        for task, levels in value.items():
            if isinstance(levels, str):
                levels = json.loads(levels) if levels.strip().startswith("[") else levels.split(",")
            parsed[task] = [AIChainLevel.parse(level) for level in levels if level]
        return parsed

    @model_validator(mode="after")
    def _check(self) -> "AIOpsSettings":
        for key, provider in self.providers.items():
            if not provider.name:
                provider.name = key
        if not self.providers:
            return self
        if not self.chains.get("default"):
            raise ValueError(
                "AI Ops has providers but no default chain. Set ACEX_AI_OPS_CHAINS__DEFAULT "
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
