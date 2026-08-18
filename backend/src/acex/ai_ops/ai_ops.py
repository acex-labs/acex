import json
import logging
import time

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from .config import AIChainLevel, AIOpsSettings
from .settings import (
    ANALYSIS_MAX_TOKENS,
    CONFIG_ANALYSIS_SYSTEM_PROMPT,
    CONFIG_ANALYSIS_TASK_PROMPTS,
)

logger = logging.getLogger("acex.ai_ops")

#: How long a provider's model list is cached (seconds)
MODELS_CACHE_TTL = 60

#: Yielded once at the end of a task stream when the provider reported token
#: usage. The API layer converts it to an SSE event; never part of content.
USAGE_MARKER = "\x00usage\x00"


class AllLevelsExhaustedError(Exception):
    """Raised when every level in a failover chain failed."""

    def __init__(self, task: str, failures: list[tuple[AIChainLevel, str]]):
        self.task = task
        self.failures = failures
        detail = "; ".join(f"{lvl.provider}/{lvl.model}: {err}" for lvl, err in failures)
        super().__init__(f"All {len(failures)} level(s) failed for task '{task}': {detail}")


class AIOpsManager:
    def __init__(
        self,
        settings: AIOpsSettings,
        system_prompt: str | list[str] = None,
    ):
        """
        Initialize AI Ops Manager with provider/chain configuration.

        Args:
            settings: Providers + per-task failover chains (see ai_ops/config.py).
            system_prompt: System prompt(s) for the AI assistant. Can be a string or list of strings.
        """
        self.settings = settings
        transport = StreamableHttpTransport(url=settings.mcp_server_url)
        self.mcp = Client(transport)

        # One AsyncOpenAI client per unique provider, created lazily
        self._clients: dict[str, AsyncOpenAI] = {}
        # Model list cache: provider name -> (timestamp, models | None)
        self._models_cache: dict[str, tuple[float, list[str] | None]] = {}
        # Usage from the most recent streaming call (provider-reported, if supported)
        self._last_usage: dict | None = None

        # Convert system_prompt to list of message dicts
        if system_prompt is None:
            self.system_messages = [
                {
                    "role": "system",
                    "content": """You are a helpful network automation assistant
                    with access to network configuration tools.""",
                }
            ]
        elif isinstance(system_prompt, str):
            self.system_messages = [{"role": "system", "content": system_prompt}]
        else:
            self.system_messages = [{"role": "system", "content": msg} for msg in system_prompt]

    # ------------------------------------------------------------------
    # Provider / model discovery
    # ------------------------------------------------------------------

    def _client_for(self, provider_name: str) -> AsyncOpenAI:
        client = self._clients.get(provider_name)
        if client is None:
            provider = self.settings.providers[provider_name]
            client = AsyncOpenAI(api_key=provider.api_key, base_url=provider.base_url)
            self._clients[provider_name] = client
        return client

    async def list_models(
        self, provider_name: str, force_refresh: bool = False, include_all: bool = False
    ) -> list[dict] | None:
        """List models for a provider, enriched with metadata.

        Each entry: {"id": ..., "supports_tools": ..., "supports_vision": ...,
        "context_window": ..., "input_cost_per_mtok": ..., "output_cost_per_mtok": ...,
        "currency": ..., "extra": {...}}. Metadata comes from the provider's
        /models response when available, overridden by the provider's
        configured `model_meta`.

        By default only chat-completion models are returned (embeddings,
        speech-to-text, rerankers, image generators etc. are filtered out).
        Pass include_all=True to get the unfiltered list.

        Returns None if the provider is unreachable and has no static_models.
        Cached for MODELS_CACHE_TTL seconds per provider (filter applied after cache).
        """
        provider = self.settings.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider '{provider_name}'")

        cached = self._models_cache.get(provider_name)
        if not force_refresh and cached and (time.time() - cached[0]) < MODELS_CACHE_TTL:
            models = cached[1]
        else:
            models: list[dict] | None = None
            try:
                result = await self._client_for(provider_name).models.list()
                models = [self._model_entry(m, provider) for m in result.data]
                models.sort(key=lambda m: m["id"])
            except Exception as exc:
                logger.warning("Failed to list models from provider '%s': %s", provider_name, exc)
                if provider.static_models:
                    models = [self._model_entry({"id": mid}, provider) for mid in provider.static_models]

            self._models_cache[provider_name] = (time.time(), models)

        if models is None:
            return None
        if include_all:
            return models
        return [m for m in models if m["is_chat_model"]]

    @staticmethod
    def _model_entry(raw, provider) -> dict:
        """Normalize one /models entry (SDK object or dict) into a metadata dict.

        OpenAI spec only guarantees `id`; several compatible providers add
        capability/pricing fields. We harvest what we recognize, keep the
        rest in `extra`, then apply the provider's configured overrides.
        """
        dump = raw if isinstance(raw, dict) else raw.model_dump()
        model_id = dump.get("id", "")

        # --- harvest capabilities (naming varies by provider) ---
        # Berget: capabilities.function_calling / capabilities.vision
        # OpenRouter: supported_parameters contains "tools"; vision from architecture
        caps = dump.get("capabilities") or {}
        tools = dump.get("supports_tools", dump.get("tool_calling", caps.get("tools", caps.get("function_calling"))))
        if tools is None:
            supported = dump.get("supported_parameters")
            if isinstance(supported, list):
                tools = "tools" in supported

        vision = dump.get("supports_vision", dump.get("vision", caps.get("vision")))
        if vision is None:
            arch = dump.get("architecture") or {}
            modalities = arch.get("input_modalities")
            if isinstance(modalities, list):
                vision = any(m in ("image", "video") for m in modalities)

        context = dump.get("context_window", dump.get("context_length", dump.get("max_context_length")))

        # --- harvest pricing ---
        # OpenRouter: {"prompt": "<per-token str>", "completion": "<per-token str>"} (USD)
        # Berget:     {"currency": "EUR", "input": <per-MTok num>, "output": <per-MTok num>}
        pricing = dump.get("pricing") or {}

        def _per_mtok(value):
            try:
                return round(float(value) * 1_000_000, 6)
            except (TypeError, ValueError):
                return None

        input_cost = dump.get("input_cost_per_mtok")
        output_cost = dump.get("output_cost_per_mtok")
        currency = dump.get("currency")

        if isinstance(pricing.get("input"), (int, float)) or isinstance(pricing.get("output"), (int, float)):
            # Already per-MTok numbers (Berget)
            input_cost = input_cost if input_cost is not None else pricing.get("input")
            output_cost = output_cost if output_cost is not None else pricing.get("output")
            currency = currency or pricing.get("currency")
        else:
            # Per-token strings (OpenRouter)
            input_cost = input_cost if input_cost is not None else _per_mtok(pricing.get("prompt"))
            output_cost = output_cost if output_cost is not None else _per_mtok(pricing.get("completion"))
            currency = currency or ("USD" if pricing else None)

        # --- is this a chat-completion model? ---
        # Berget: model_type == "text" (others: "embedding", "speech-to-text", "rerank")
        # OpenRouter: architecture.output_modalities contains "text"
        # Unknown (plain OpenAI spec, static_models): assume yes
        model_type = dump.get("model_type")
        if model_type is not None:
            is_chat = model_type == "text"
        else:
            arch = dump.get("architecture") or {}
            out_modalities = arch.get("output_modalities")
            if isinstance(out_modalities, list):
                is_chat = "text" in out_modalities
            else:
                is_chat = True

        known = {
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
        extra = {k: v for k, v in dump.items() if k not in known}

        entry = {
            "id": model_id,
            "is_chat_model": is_chat,
            "supports_tools": tools,
            "supports_vision": vision,
            "context_window": context,
            "input_cost_per_mtok": input_cost,
            "output_cost_per_mtok": output_cost,
            "currency": currency,
            "extra": extra or None,
        }

        # Configured overrides win over harvested data
        override = provider.model_meta.get(model_id)
        if override:
            for field, value in override.model_dump(exclude_none=True).items():
                if field == "extra":
                    entry["extra"] = {**(entry["extra"] or {}), **value}
                else:
                    entry[field] = value
        return entry

    def providers_info(self) -> list[dict]:
        """Configured providers with their chains role — enrichment (models, health)
        is added by the API layer via list_models()."""
        return [
            {
                "name": p.name,
                "base_url": p.base_url,
                "has_static_models": p.static_models is not None,
            }
            for p in self.settings.providers.values()
        ]

    # ------------------------------------------------------------------
    # Chain resolution + failover
    # ------------------------------------------------------------------

    def resolve_chain(self, task: str, model_override: str | None = None) -> list[tuple[AsyncOpenAI, AIChainLevel]]:
        """Resolve (client, level) pairs to try, in order.

        An explicit model_override produces a single-level chain: the model is
        looked up in the provider namespace it names ("provider/model") or, if
        unqualified, in the first chain level's provider.
        """
        chain = self.settings.chain_for(task)

        if model_override:
            if "/" in model_override:
                provider_name, model = model_override.split("/", 1)
            else:
                provider_name, model = chain[0].provider, model_override
            level = AIChainLevel(provider=provider_name, model=model)
            self.settings.provider_for(level)  # validate
            return [(self._client_for(provider_name), level)]

        return [(self._client_for(level.provider), level) for level in chain]

    @staticmethod
    def _is_failoverable(exc: Exception) -> bool:
        """Connection problems, timeouts, 429 and 5xx mean 'try next level'.
        4xx means a configuration/request problem — fail immediately."""
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return True
        if isinstance(exc, APIStatusError):
            return exc.status_code == 429 or exc.status_code >= 500
        return False

    async def _create_with_failover(self, task: str, model_override: str | None, **kwargs):
        """Try chat.completions.create on each chain level until one succeeds.

        Failover is only possible before the first token — for streaming calls
        this means a successful create() plus first yielded chunk is handled by
        the caller wrapping the stream (see _stream_with_failover).

        With an explicit model_override there is no failover: the original
        error propagates to the caller.
        """
        candidates = self.resolve_chain(task, model_override)
        failures: list[tuple[AIChainLevel, str]] = []

        for client, level in candidates:
            try:
                response = await client.chat.completions.create(model=level.model, **kwargs)
                if len(candidates) > 1 and failures:
                    logger.warning("[AI] failover: using %s/%s for task '%s'", level.provider, level.model, task)
                return response, level
            except Exception as exc:
                if model_override or not self._is_failoverable(exc):
                    raise
                logger.warning("[AI] level %s/%s failed for task '%s': %s", level.provider, level.model, task, exc)
                failures.append((level, str(exc)))

        raise AllLevelsExhaustedError(task, failures)

    async def _stream_with_failover(self, task: str, model_override: str | None, **kwargs):
        """Streaming variant: yields chunks; failovers only before the first chunk.

        With an explicit model_override there is no failover: the original
        error propagates to the caller.

        Requests `stream_options.include_usage` — the provider's final chunk
        then carries exact token counts, surfaced via `self._last_usage`.
        """
        candidates = self.resolve_chain(task, model_override)
        failures: list[tuple[AIChainLevel, str]] = []
        self._last_usage = None

        for client, level in candidates:
            yielded_any = False
            started_at = time.monotonic()
            first_token_at = None
            try:
                stream = await client.chat.completions.create(
                    model=level.model, stream=True, stream_options={"include_usage": True}, **kwargs
                )
                async for chunk in stream:
                    # Final usage chunk: empty choices + usage set
                    usage = getattr(chunk, "usage", None)
                    if usage is not None and not getattr(chunk, "choices", None):
                        self._last_usage = self._build_usage(usage, level, started_at, first_token_at)
                        continue
                    if not yielded_any:
                        yielded_any = True
                        first_token_at = time.monotonic()
                        if failures:
                            logger.warning(
                                "[AI] failover: streaming from %s/%s for task '%s'",
                                level.provider,
                                level.model,
                                task,
                            )
                    yield chunk
                return
            except Exception as exc:
                if model_override or not self._is_failoverable(exc):
                    raise
                logger.warning("[AI] level %s/%s failed for task '%s': %s", level.provider, level.model, task, exc)
                failures.append((level, str(exc)))
                # Failover is only safe before the first chunk was yielded
                if yielded_any:
                    raise AllLevelsExhaustedError(task, failures) from exc

        raise AllLevelsExhaustedError(task, failures)

    def _build_usage(self, usage, level: AIChainLevel, started_at: float, first_token_at: float | None) -> dict:
        """Normalize a usage object + compute cost and throughput.

        tokens_per_second covers the generation phase (first token → last),
        which is the number users perceive as "speed"."""
        elapsed = time.monotonic() - (first_token_at or started_at)
        completion_tokens = getattr(usage, "completion_tokens", None)
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None and not isinstance(details, dict):
            details = getattr(details, "model_dump", lambda: {})()
        result = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": completion_tokens,
            "total_tokens": getattr(usage, "total_tokens", None),
            # Provider-specific extras we surface when present (Berget):
            "reasoning_tokens": getattr(usage, "reasoning_tokens", None),
            "cached_tokens": (details or {}).get("cached_tokens"),
            "co2_grams": getattr(usage, "co2_grams", None),
            "provider": level.provider,
            "model": level.model,
            "cost": None,
            "currency": None,
            "elapsed_seconds": round(time.monotonic() - started_at, 2),
            "tokens_per_second": (round(completion_tokens / elapsed, 1) if completion_tokens and elapsed > 0 else None),
        }
        pricing = self._pricing_for(level)
        if pricing and result["prompt_tokens"] is not None and completion_tokens is not None:
            in_cost, out_cost, currency = pricing
            result["cost"] = round((result["prompt_tokens"] * in_cost + completion_tokens * out_cost) / 1_000_000, 6)
            result["currency"] = currency
        return result

    def _pricing_for(self, level: AIChainLevel) -> tuple[float, float, str | None] | None:
        """(input, output) per-MTok + currency for a chain level — from the
        cached model list (which includes configured overrides)."""
        cached = self._models_cache.get(level.provider)
        if not cached or not cached[1]:
            return None
        for m in cached[1]:
            if m["id"] == level.model:
                if m["input_cost_per_mtok"] is not None and m["output_cost_per_mtok"] is not None:
                    return (m["input_cost_per_mtok"], m["output_cost_per_mtok"], m["currency"])
                return None
        return None

    # ------------------------------------------------------------------
    # MCP tools
    # ------------------------------------------------------------------

    def _convert_tools(self, tool_list):
        """
        Convert FastMCP Tool objects → OpenAI function-call schema
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": getattr(t, "description", "") or "",
                    "parameters": getattr(t, "parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tool_list
        ]

    async def call_mcp_tool(self, tool_name: str, args=None):
        """
        Execute MCP tool using streaming JSON-RPC
        """
        if args is None:
            args = {}
        result = await self.mcp.call_tool(tool_name, arguments=args)
        return result

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def analyze_config_diff(self, task: str, diff: str, context: str = "", model: str | None = None):
        """Stream a focused config-diff analysis without MCP tool calling.

        Args:
            task:    One of 'explain', 'risk_assessment', 'alignment'
            diff:    Unified diff text (the config change to analyse)
            context: Optional freeform context string (hostname, snapshot timestamps, etc.)
            model:   Optional explicit model override ("provider/model" or "model").
                     Explicit overrides run without failover.
        """
        task_template = CONFIG_ANALYSIS_TASK_PROMPTS.get(task)
        if task_template is None:
            raise ValueError(f"Unknown analysis task '{task}'. Valid tasks: {list(CONFIG_ANALYSIS_TASK_PROMPTS)}")

        user_prompt = task_template.format(
            diff=diff,
            context=f"{context}\n" if context else "",
        )

        messages = [
            {"role": "system", "content": CONFIG_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        logger.info("[AI] analyze_config_diff: task=%s diff_len=%d", task, len(diff))

        chunk_count = 0
        async for chunk in self._stream_with_failover(
            "analysis", model, messages=messages, max_tokens=ANALYSIS_MAX_TOKENS
        ):
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    chunk_count += 1
                    yield delta.content
        logger.info("[AI] analysis stream done, yielded %d chunks", chunk_count)
        if self._last_usage:
            yield USAGE_MARKER

    async def ask(
        self,
        prompt: str,
        conversation_history: list[dict] = None,
        context: str | None = None,
        extra_system_prompts: list[str] | None = None,
        model: str | None = None,
    ):
        """Stream AI response with tool calling support and conversation history

        Args:
            prompt: The user's current question/prompt
            conversation_history: Previous messages in the conversation
                                 Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            context: Optional page context (visible data) injected as a system message
            extra_system_prompts: Additional system prompts injected after the base prompts
                                  (used by the web UI to add UI schema, skills, page context rules)
            model: Optional explicit model override ("provider/model" or "model").
                   Explicit overrides run without failover.
        """
        if conversation_history is None:
            conversation_history = []

        extra_messages = [{"role": "system", "content": p} for p in (extra_system_prompts or [])]
        context_messages = [{"role": "system", "content": f"Page context:\n{context}"}] if context else []

        try:
            async with self.mcp:
                raw_tools = await self.mcp.list_tools()
                tools = self._convert_tools(raw_tools)

                # Build message history: system + ui context + page context + history + current prompt
                messages = [
                    *self.system_messages,
                    *extra_messages,
                    *context_messages,
                    *conversation_history,
                    {"role": "user", "content": prompt},
                ]

                # First request - check if tools are needed
                response, _level = await self._create_with_failover(
                    "chat", model, messages=messages, tools=tools, tool_choice="auto"
                )

                msg = response.choices[0].message

                # Handle tool calls if present
                if msg.tool_calls:
                    # Collect all tool results first
                    tool_messages = []

                    for call in msg.tool_calls:
                        args = call.function.arguments or {}
                        if isinstance(args, str):
                            args = json.loads(args)

                        yield f"[Calling tool: {call.function.name}]\n"

                        try:
                            mcp_result = await self.call_mcp_tool(call.function.name, args)
                            texts = []
                            for c in mcp_result.content:
                                if hasattr(c, "text"):
                                    texts.append(c.text)

                            tool_output_text = "".join(texts).strip()
                            try:
                                tool_output = json.loads(tool_output_text)
                            except json.JSONDecodeError:
                                tool_output = tool_output_text

                            # Add tool result to messages
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.id,
                                    "name": call.function.name,
                                    "content": json.dumps(tool_output),
                                }
                            )
                        except Exception as e:
                            yield f"[Error calling {call.function.name}: {str(e)}]\n"
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.id,
                                    "name": call.function.name,
                                    "content": json.dumps({"error": str(e)}),
                                }
                            )

                    # Now make a single LLM call with all tool results.
                    # NOTE: no failover here — the chain level was selected at the
                    # start of the request and the conversation (incl. tool calls)
                    # is tied to it.
                    final_messages = [
                        *messages,  # Include full conversation history (system + history + user prompt)
                    ]

                    # Add assistant message with tool calls
                    final_messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": call.id,
                                    "type": "function",
                                    "function": {
                                        "name": call.function.name,
                                        "arguments": (
                                            call.function.arguments
                                            if isinstance(call.function.arguments, str)
                                            else json.dumps(call.function.arguments)
                                        ),
                                    },
                                }
                                for call in msg.tool_calls
                            ],
                        }
                    )

                    # Add all tool results
                    final_messages.extend(tool_messages)

                    try:
                        client = self._client_for(_level.provider)
                        started_at = time.monotonic()
                        first_token_at = None
                        stream = await client.chat.completions.create(
                            model=_level.model,
                            messages=final_messages,
                            stream=True,
                            stream_options={"include_usage": True},
                        )

                        async for chunk in stream:
                            usage = getattr(chunk, "usage", None)
                            if usage is not None and not getattr(chunk, "choices", None):
                                self._last_usage = self._build_usage(usage, _level, started_at, first_token_at)
                                continue
                            if chunk.choices:
                                if first_token_at is None:
                                    first_token_at = time.monotonic()
                                delta = chunk.choices[0].delta
                                if delta.content:
                                    yield delta.content
                    except Exception as e:
                        yield f"\n[Error in LLM stream: {str(e)}]\n"
                else:
                    # No tools needed - stream initial response
                    async for chunk in self._stream_with_failover(
                        "chat", model, messages=messages, tools=tools, tool_choice="auto"
                    ):
                        if chunk.choices:
                            delta = chunk.choices[0].delta
                            if delta.content:
                                yield delta.content

                if self._last_usage:
                    yield USAGE_MARKER

        except (AllLevelsExhaustedError, APIStatusError):
            raise
        except Exception as mcp_error:
            # MCP server unavailable - fall back to conversational mode without tools
            logger.warning("[AI] MCP unavailable, falling back to no-tools chat: %s", mcp_error)
            messages = [
                *self.system_messages,
                *extra_messages,
                *context_messages,
                {
                    "role": "system",
                    "content": (
                        "The tool server (MCP) is currently unavailable. Answer based on the page context "
                        "provided. Do not claim you cannot access data that is already present in the page context."
                    ),
                },
                *conversation_history,
                {"role": "user", "content": prompt},
            ]
            async for chunk in self._stream_with_failover("chat", model, messages=messages):
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
            if self._last_usage:
                yield USAGE_MARKER
