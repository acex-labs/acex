"""Which models a provider offers, what they can do and what they cost."""

import logging
import time

from .config import AIModelConfig, AIOpsSettings, AIProvider
from .endpoints import Endpoints
from .errors import ProviderError
from .types import Usage

logger = logging.getLogger("acex.ai_ops")

#: Fields of a model entry that come from AIModelConfig when it sets them.
METADATA_FIELDS = (
    "supports_tools",
    "supports_vision",
    "context_window",
    "input_cost_per_mtok",
    "output_cost_per_mtok",
    "currency",
)

#: /models fields that are harvested into the entry rather than kept in `extra`.
HARVESTED_FIELDS = {
    "id",
    "created",
    "object",
    "owned_by",
    "capabilities",
    "pricing",
    "supports_tools",
    "tool_calling",
    "supports_vision",
    "vision",
    "context_window",
    "context_length",
    "max_context_length",
    "currency",
    "input_cost_per_mtok",
    "output_cost_per_mtok",
    "supported_parameters",
    "architecture",
    "model_type",
}


class ModelCatalog:
    """Model lists per provider: the provider's /models listing merged with the
    models configured for it, configuration winning per field.

    Entries: {"id", "is_chat_model", "supports_tools", "supports_vision",
    "context_window", "input_cost_per_mtok", "output_cost_per_mtok",
    "currency", "extra"}. Cached per provider for TTL seconds.
    """

    TTL = 60

    def __init__(self, settings: AIOpsSettings, endpoints: Endpoints):
        self.settings = settings
        self.endpoints = endpoints
        self._cache: dict[str, tuple[float, list[dict] | None]] = {}

    async def models(self, provider_name: str, force_refresh: bool = False, include_all: bool = False):
        """The provider's chat models, or every model with include_all.

        None when the provider could not be listed and has no configured models.
        """
        provider = self.settings.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider '{provider_name}'")

        cached = self._cache.get(provider_name)
        if force_refresh or not cached or time.time() - cached[0] >= self.TTL:
            cached = self._cache[provider_name] = (time.time(), await self._load(provider))

        models = cached[1]
        if models is None or include_all:
            return models
        return [m for m in models if m["is_chat_model"]]

    def entry(self, provider_name: str, model_id: str) -> dict:
        """What is known about one model without making a request: the cached
        listing if there is one, else the model's configuration alone."""
        cached = self._cache.get(provider_name)
        for entry in (cached and cached[1]) or []:
            if entry["id"] == model_id:
                return entry
        provider = self.settings.providers[provider_name]
        return self.configured(self.harvest({"id": model_id}), provider.model(model_id))

    def cost(self, provider_name: str, model_id: str, usage: Usage) -> tuple[float | None, str | None]:
        entry = self.entry(provider_name, model_id)
        if entry["input_cost_per_mtok"] is None or entry["output_cost_per_mtok"] is None:
            return None, None
        cost = (
            usage.prompt_tokens * entry["input_cost_per_mtok"] + usage.completion_tokens * entry["output_cost_per_mtok"]
        )
        return round(cost / 1_000_000, 6), entry["currency"]

    async def _load(self, provider: AIProvider) -> list[dict] | None:
        listed: list[dict] | None = []
        if provider.discoverable:
            try:
                listed = [self.harvest(raw) for raw in await self.endpoints.listing_adapter(provider).list_models()]
            except ProviderError as exc:
                logger.warning(f"[AI] failed to list models from provider '{provider.name}': {exc}")
                listed = None
        if listed is None and not provider.models:
            return None

        entries = {entry["id"]: entry for entry in listed or []}
        for model_id in provider.models:
            entries.setdefault(model_id, self.harvest({"id": model_id}))
        return sorted(
            (self.configured(entry, provider.model(entry["id"])) for entry in entries.values()),
            key=lambda entry: entry["id"],
        )

    @staticmethod
    def configured(entry: dict, config: AIModelConfig) -> dict:
        """The entry with the configured fields laid over it."""
        entry = dict(entry)
        for name in METADATA_FIELDS:
            value = getattr(config, name)
            if value is not None:
                entry[name] = value
        if config.extra:
            entry["extra"] = {**(entry["extra"] or {}), **config.extra}
        return entry

    @classmethod
    def harvest(cls, dump: dict) -> dict:
        """Normalize one /models entry into a model entry.

        The OpenAI spec only guarantees `id`; several compatible providers add
        capability and pricing fields under their own names. What is recognized
        is harvested, the rest kept in `extra`.
        """
        # Berget: capabilities.function_calling / capabilities.vision
        # OpenRouter: supported_parameters contains "tools"; vision from architecture
        caps = dump.get("capabilities") or {}
        arch = dump.get("architecture") or {}
        tools = dump.get("supports_tools", dump.get("tool_calling", caps.get("tools", caps.get("function_calling"))))
        if tools is None and isinstance(dump.get("supported_parameters"), list):
            tools = "tools" in dump["supported_parameters"]
        vision = dump.get("supports_vision", dump.get("vision", caps.get("vision")))
        if vision is None and isinstance(arch.get("input_modalities"), list):
            vision = any(m in ("image", "video") for m in arch["input_modalities"])

        # OpenRouter: {"prompt": "<per-token str>", "completion": "<per-token str>"} (USD)
        # Berget:     {"currency": "EUR", "input": <per-MTok num>, "output": <per-MTok num>}
        pricing = dump.get("pricing") or {}
        input_cost = dump.get("input_cost_per_mtok")
        output_cost = dump.get("output_cost_per_mtok")
        currency = dump.get("currency")
        if isinstance(pricing.get("input"), (int, float)) or isinstance(pricing.get("output"), (int, float)):
            input_cost = input_cost if input_cost is not None else pricing.get("input")
            output_cost = output_cost if output_cost is not None else pricing.get("output")
            currency = currency or pricing.get("currency")
        else:
            input_cost = input_cost if input_cost is not None else cls._per_mtok(pricing.get("prompt"))
            output_cost = output_cost if output_cost is not None else cls._per_mtok(pricing.get("completion"))
            currency = currency or ("USD" if pricing else None)

        # Berget: model_type == "text" (others: "embedding", "speech-to-text", "rerank")
        # OpenRouter: architecture.output_modalities contains "text"
        # Unknown (plain OpenAI spec, configured models): assume a chat model
        if dump.get("model_type") is not None:
            is_chat = dump["model_type"] == "text"
        elif isinstance(arch.get("output_modalities"), list):
            is_chat = "text" in arch["output_modalities"]
        else:
            is_chat = True

        extra = {k: v for k, v in dump.items() if k not in HARVESTED_FIELDS}
        return {
            "id": dump.get("id", ""),
            "is_chat_model": is_chat,
            "supports_tools": tools,
            "supports_vision": vision,
            "context_window": dump.get("context_window", dump.get("context_length", dump.get("max_context_length"))),
            "input_cost_per_mtok": input_cost,
            "output_cost_per_mtok": output_cost,
            "currency": currency,
            "extra": extra or None,
        }

    @staticmethod
    def _per_mtok(value) -> float | None:
        try:
            return round(float(value) * 1_000_000, 6)
        except (TypeError, ValueError):
            return None
