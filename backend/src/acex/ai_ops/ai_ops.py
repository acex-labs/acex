import json
import logging
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from .config import AIChainLevel, AIOpsSettings
from .settings import (
    ANALYSIS_MAX_TOKENS,
    CHAT_MAX_TOKENS,
    CONFIG_ANALYSIS_SYSTEM_PROMPT,
    CONFIG_ANALYSIS_TASK_PROMPTS,
)

logger = logging.getLogger("acex.ai_ops")

#: How long a provider's model list is cached (seconds)
MODELS_CACHE_TTL = 60


@dataclass(slots=True)
class UsageEvent:
    """Provider-reported token usage for one request.

    Yielded into the stream rather than stashed on the manager: the manager is
    a process-wide singleton, so instance state would let concurrent users
    overwrite each other's token counts.
    """

    data: dict


@dataclass(slots=True)
class PlanEvent:
    """The approach the assistant committed to before acting.

    Rendered as the checklist that subsequent ToolCallEvents tick off, so the
    plan and the progress against it are the same UI element.
    """

    goal: str | None
    steps: list[dict]


@dataclass(slots=True)
class ToolCallEvent:
    """Progress of one tool call, for the UI to render as its own element.

    Kept out of the content stream: the assistant's prose is the answer, and
    splicing status lines into it leaves them in the text the user reads.

    status is "running" when the call starts, then "ok" or "error".
    """

    name: str
    status: str
    error: str | None = None


@dataclass(slots=True)
class NavigateEvent:
    """A page the assistant suggests opening.

    The API layer turns this into an SSE event and the frontend renders it as a
    link the user must click — navigation is never automatic.
    """

    data: dict


#: Local (non-MCP) tool merged into the chat tool list. Calling it does not
#: navigate anything server-side — the backend intercepts the call, never
#: forwards it to MCP, and just signals the suggestion to the frontend.
#: The description is deliberately conservative: only call this off a clear,
#: direct request; otherwise ask in the reply text instead.
NAVIGATE_TOOL = {
    "type": "function",
    "function": {
        "name": "navigate_to",
        "description": (
            "Suggest opening another page in the web UI for the user. This does NOT "
            "navigate anything by itself — it shows the user a clickable link; they "
            "decide whether to follow it. Only call this when the user has directly "
            "asked to go to / open / see a specific, known page or entity. If it's not "
            "a clear, direct request, do not call this tool — instead ask in your reply "
            "whether they'd like you to open it, and wait for their confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": ["node_detail", "site_detail", "nodes_list", "sites_list", "dashboard"],
                    "description": "Which known page to open.",
                },
                "id": {
                    "type": "string",
                    "description": (
                        "Entity id, for node_detail/site_detail — only if you actually have "
                        "the id itself (e.g. from a tool result). Prefer `name` otherwise."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Entity name, for node_detail/site_detail — use this instead of `id` "
                        "whenever you only know it by name (site name, node hostname), which is "
                        "the common case. The UI looks up the id itself. Give the exact name as "
                        "shown, not a guess."
                    ),
                },
                "tab": {
                    "type": "string",
                    "enum": ["overview", "configuration", "hardware", "lldp", "history"],
                    "description": "Optional tab to open on node_detail.",
                },
                "label": {
                    "type": "string",
                    "description": "Short link text for the button, e.g. 'Open node SW-CORE-1'.",
                },
            },
            "required": ["page", "label"],
        },
    },
}

#: Local tool the model uses to commit to an approach before acting. The steps
#: become a checklist in the UI that the subsequent tool calls tick off, so the
#: user can see what the assistant intends to check and how far it has got.
#: Planning also improves the work itself: naming the lookups up front is what
#: turns "this might affect downstream devices" into actually checking each
#: neighbour, rather than hedging in the final answer.
PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "plan",
        "description": (
            "State the lookups you are about to make, before making them. Call this FIRST "
            "whenever answering will take more than one tool call — for example a "
            "configuration change whose impact depends on other devices, where you need to "
            "work out which neighbours to check and then check each one. Listing the steps "
            "is how you commit to verifying something instead of speculating about it. "
            "The steps are shown to the user as a checklist which ticks off as you go, so "
            "do not repeat the plan in your reply text. Skip this tool for anything a "
            "single lookup answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "One short line naming what you are trying to establish.",
                },
                "steps": {
                    "type": "array",
                    "description": (
                        "The steps, in the order you will do them. Be concrete: name the "
                        "device, port or snapshot each step concerns rather than writing "
                        "'check the neighbours'. If a step depends on what an earlier step "
                        "returns, say so in its description."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "What this step establishes, in a few words.",
                            },
                            "tool": {
                                "type": "string",
                                "description": (
                                    "The tool you intend to use for this step, if you already "
                                    "know which one. Use the exact tool name."
                                ),
                            },
                        },
                        "required": ["description"],
                    },
                },
            },
            "required": ["steps"],
        },
    },
}

#: Tools implemented locally by AIOpsManager — as opposed to MCP tools, which
#: come from the tool server. Handled entirely inside the tool loop and never
#: forwarded to MCP, so they work even when MCP is unconfigured or unreachable.
LOCAL_TOOLS: dict[str, dict] = {
    "navigate_to": NAVIGATE_TOOL,
    "plan": PLAN_TOOL,
}

#: Which local tools each task is offered. `navigate_to` is a web-UI affordance
#: and has no meaning in an analysis; planning helps both.
CHAT_LOCAL_TOOLS = ("plan", "navigate_to")
ANALYSIS_LOCAL_TOOLS = ("plan",)


#: Marker a model writes when its tool call was not converted into a structured
#: tool_calls field. It is never part of an answer.
_TOOL_CALL_TEXT = "<tool_call"

#: Closes the tool-calling phase. Without being told the turn is over, a model
#: reads the absence of tools as "write the call yourself" and produces nothing
#: but tool-call syntax.
FINAL_ANSWER_NUDGE = (
    "You now have the tool results. Answer the question in prose, based on what those results "
    "actually show. The tool-calling phase is over — do not call or write any further tool calls. "
    "If something you wanted to check is still unknown, say so plainly instead of trying again."
)

#: Used when the first closing attempt produced no text at all.
FINAL_ANSWER_RETRY = (
    "You produced no answer. Write it now, in plain prose, using only the tool results already "
    "in this conversation. Do not write tool-call syntax of any kind."
)


def _hold_partial_marker(buffer: str) -> tuple[str, str]:
    """Split a content buffer into (safe to emit, hold back).

    The marker can straddle two streamed chunks, so any trailing text that
    could still turn into it is held until the next chunk decides.
    """
    for length in range(len(_TOOL_CALL_TEXT) - 1, 0, -1):
        if buffer.endswith(_TOOL_CALL_TEXT[:length]):
            return buffer[:-length], buffer[-length:]
    return buffer, ""


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

        if settings.mcp_server_url is None:
            logger.info("[AI] no MCP server url configured — starting with local tools only")

        # One AsyncOpenAI client per unique provider, created lazily
        self._clients: dict[str, AsyncOpenAI] = {}
        # Model list cache: provider name -> (timestamp, models | None)
        self._models_cache: dict[str, tuple[float, list[str] | None]] = {}

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
        then carries exact token counts, yielded as a trailing UsageEvent.
        """
        candidates = self.resolve_chain(task, model_override)
        failures: list[tuple[AIChainLevel, str]] = []

        for client, level in candidates:
            yielded_any = False
            started_at = time.monotonic()
            first_token_at = None
            final_usage: dict | None = None
            try:
                stream = await client.chat.completions.create(
                    model=level.model, stream=True, stream_options={"include_usage": True}, **kwargs
                )
                async for chunk in stream:
                    # Final usage chunk: empty choices + usage set
                    usage = getattr(chunk, "usage", None)
                    if usage is not None and not getattr(chunk, "choices", None):
                        final_usage = self._build_usage(usage, level, started_at, first_token_at)
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
                if final_usage is not None:
                    yield UsageEvent(final_usage)
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
        """Convert MCP Tool objects → OpenAI function-call schema.

        MCP calls the JSON schema `inputSchema`; OpenAI calls it `parameters`.
        Reading the wrong name does not fail — it silently advertises every
        tool as accepting no arguments, so the model cannot express a call and
        some models fall back to writing `<tool_call>` into their reply as text.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
                },
            }
            for t in tool_list
        ]

    def _mcp_client(self, access_token: str | None) -> Client | None:
        """Build an MCP client that acts as the caller.

        Constructed per request on purpose. Transport headers are fixed at
        construction time, so a shared client cannot carry per-user
        credentials — it would send whichever token was set last to every
        concurrent user. The MCP server itself holds no credentials; it
        forwards this token to the ACE-X API, which authorizes the read.
        """
        if self.settings.mcp_server_url is None:
            return None
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        return Client(StreamableHttpTransport(url=self.settings.mcp_server_url, headers=headers))

    async def _open_mcp(self, stack: AsyncExitStack, access_token: str | None):
        """Enter an MCP session for this request.

        Returns (client, tools). Both are empty when MCP is unconfigured or
        unreachable — tool calling then degrades to LOCAL_TOOLS rather than
        failing the whole request.
        """
        mcp = self._mcp_client(access_token)
        if mcp is None:
            return None, []
        try:
            await stack.enter_async_context(mcp)
            return mcp, self._convert_tools(await mcp.list_tools())
        except Exception as exc:
            logger.warning("[AI] MCP unavailable, continuing without its tools: %s", exc)
            return None, []

    @staticmethod
    async def call_mcp_tool(mcp: Client, tool_name: str, args=None):
        """Execute one MCP tool in an already-open session."""
        return await mcp.call_tool(tool_name, arguments=args or {})

    # ------------------------------------------------------------------
    # Tool-calling loop (shared by ask() and analyze_config_diff())
    # ------------------------------------------------------------------

    async def _run_tool_loop(
        self,
        task: str,
        model: str | None,
        messages: list[dict],
        tools: list[dict],
        mcp: Client | None,
        max_rounds: int = 5,
        max_tokens: int | None = None,
    ):
        """Agentic tool-calling loop: lets the model call tools, look at the
        results, and call more tools before answering — instead of a single
        fixed round. Used by both the chat ("chat" chain) and analysis
        ("analysis" chain) tasks so an analysis can, for example, look up a
        port's LLDP neighbor and check that neighbor's config before
        asserting a claim, rather than only reasoning from the diff text.

        Mutates `messages` in place and appends to it as the conversation
        with the model progresses. Local tools (LOCAL_TOOLS) are handled
        inline and never forwarded to MCP; anything else needs an open `mcp`
        session — a real MCP tool call attempted without one yields a clear
        per-call error instead of crashing.

        Yields content chunks and "[Calling tool: x]" status lines as strings,
        plus a NavigateEvent if the model called navigate_to and a UsageEvent
        at the end if the provider reported token usage.
        """
        corrections = 0
        used_tools = False
        kwargs = {"tools": tools, "tool_choice": "auto"} if tools else {}
        # Only send max_tokens when there is a limit. The OpenAI SDK serializes
        # an explicit None as `"max_tokens": null`, which strict providers
        # reject with a 400 rather than reading it as "no limit".
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        _level = None

        for _ in range(max_rounds):
            if _level is None:
                response, _level = await self._create_with_failover(task, model, messages=messages, **kwargs)
            else:
                client = self._client_for(_level.provider)
                response = await client.chat.completions.create(model=_level.model, messages=messages, **kwargs)
            msg = response.choices[0].message

            if not msg.tool_calls:
                # A model whose tool call was not converted into a structured
                # tool_calls field writes its own syntax into the content
                # instead. Treating that as a final answer ends the loop early
                # and streams the raw syntax to the user, so nudge it once.
                if _TOOL_CALL_TEXT in (msg.content or "") and corrections < 1:
                    corrections += 1
                    logger.warning("[AI] model wrote a tool call as text for task '%s'; asking it to retry", task)
                    messages.append({"role": "assistant", "content": msg.content or ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "That tool call was written as text, so it did not run and produced no "
                                "result. Call the tool through the function-calling interface instead."
                            ),
                        }
                    )
                    continue
                break

            messages.append(
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

            used_tools = True

            for call in msg.tool_calls:
                args = call.function.arguments or {}
                if isinstance(args, str):
                    args = json.loads(args)

                if call.function.name in LOCAL_TOOLS:
                    # Handled locally — never forwarded to MCP.
                    if call.function.name == "navigate_to":
                        yield NavigateEvent(args)
                        result = {
                            "status": "shown_to_user",
                            "note": (
                                "A link to this page is already shown to the user in the UI. "
                                "Don't repeat the raw page/id/path in your reply — just briefly "
                                "confirm in one short sentence."
                            ),
                        }
                    else:  # plan
                        steps = [s for s in (args.get("steps") or []) if isinstance(s, dict)]
                        yield PlanEvent(args.get("goal"), steps)
                        result = {
                            "status": "shown_to_user",
                            "note": (
                                "The plan is now a checklist in the UI. Carry out step one; the "
                                "checklist ticks off as you call each tool. Don't restate the plan "
                                "in your reply — report what you found. If a lookup changes the "
                                "picture, follow the new lead rather than the original list."
                            ),
                        }
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.function.name,
                            "content": json.dumps(result),
                        }
                    )
                    continue

                if mcp is None:
                    yield ToolCallEvent(call.function.name, "error", "MCP tool server unavailable")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.function.name,
                            "content": json.dumps({"error": "MCP tool server unavailable"}),
                        }
                    )
                    continue

                yield ToolCallEvent(call.function.name, "running")

                try:
                    mcp_result = await self.call_mcp_tool(mcp, call.function.name, args)
                    texts = [c.text for c in mcp_result.content if hasattr(c, "text")]
                    tool_output_text = "".join(texts).strip()
                    try:
                        tool_output = json.loads(tool_output_text)
                    except json.JSONDecodeError:
                        tool_output = tool_output_text

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.function.name,
                            "content": json.dumps(tool_output),
                        }
                    )
                    yield ToolCallEvent(call.function.name, "ok")
                except Exception as e:
                    yield ToolCallEvent(call.function.name, "error", str(e))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.function.name,
                            "content": json.dumps({"error": str(e)}),
                        }
                    )

        # Final answer. NOTE: no failover here — the chain level was
        # selected on the first round and the conversation (incl. any tool
        # calls) is tied to it.
        #
        # The model has to be told this is the closing turn. Left to infer it
        # from the absence of tools, it keeps writing tool-call syntax — which
        # the sanitizer then strips, leaving the user an empty reply.
        if used_tools:
            messages.append({"role": "user", "content": FINAL_ANSWER_NUDGE})

        usage_holder: dict = {}
        produced: list[str] = []
        async for piece in self._stream_answer(_level, messages, max_tokens, tools, task, usage_holder, produced):
            yield piece

        if not "".join(produced).strip():
            logger.warning("[AI] empty final answer for task '%s'; retrying once", task)
            messages.append({"role": "user", "content": FINAL_ANSWER_RETRY})
            async for piece in self._stream_answer(_level, messages, max_tokens, tools, task, usage_holder, produced):
                yield piece

        if not "".join(produced).strip():
            # Better an honest sentence than an empty reply that reads as a crash.
            yield (
                "I gathered the information but couldn't turn it into an answer. "
                "The tool results above are what I found — ask again and I'll try to summarise them."
            )

        if usage_holder.get("data") is not None:
            yield UsageEvent(usage_holder["data"])

    async def _stream_answer(self, level, messages, max_tokens, tools, task, usage_holder, produced):
        """Stream one attempt at the closing prose answer.

        Tools are still declared so the model keeps their context, but
        `tool_choice: "none"` makes the provider refuse a call — the explicit
        way of saying "answer now". Any tool-call syntax that still appears is
        suppressed from the marker onwards; it is never part of an answer.

        Text is appended to `produced` so the caller can tell whether the model
        actually said anything, and usage lands in `usage_holder`.
        """
        try:
            client = self._client_for(level.provider)
            started_at = time.monotonic()
            first_token_at = None
            options: dict = {}
            if max_tokens is not None:
                options["max_tokens"] = max_tokens
            if tools:
                options["tools"] = tools
                options["tool_choice"] = "none"

            stream = await client.chat.completions.create(
                model=level.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **options,
            )

            buffer = ""
            suppressed = False

            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None and not getattr(chunk, "choices", None):
                    usage_holder["data"] = self._build_usage(usage, level, started_at, first_token_at)
                    continue
                if chunk.choices:
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                    delta = chunk.choices[0].delta
                    if not delta.content or suppressed:
                        continue

                    buffer += delta.content
                    marker = buffer.find(_TOOL_CALL_TEXT)
                    if marker >= 0:
                        suppressed = True
                        logger.warning("[AI] suppressed tool-call syntax from the final answer for task '%s'", task)
                        if buffer[:marker]:
                            produced.append(buffer[:marker])
                            yield buffer[:marker]
                        buffer = ""
                        continue

                    emit, buffer = _hold_partial_marker(buffer)
                    if emit:
                        produced.append(emit)
                        yield emit

            if buffer and not suppressed:
                produced.append(buffer)
                yield buffer
        except Exception as e:
            yield f"\n[Error in LLM stream: {str(e)}]\n"

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def analyze_config_diff(
        self,
        task: str,
        diff: str,
        context: str = "",
        model: str | None = None,
        access_token: str | None = None,
    ):
        """Stream a focused config-diff analysis. Has MCP tool access (e.g.
        LLDP neighbors, node configs) so it can verify a claim — like whether
        a downstream device still needs a VLAN being removed — against real
        data instead of only reasoning from the diff text. Offers `plan` but
        not `navigate_to`: working out which lookups a change requires is the
        substance of an impact analysis, while navigation is a web-UI concern.

        Args:
            task:    One of 'explain', 'risk_assessment', 'alignment'
            diff:    Unified diff text (the config change to analyse)
            context: Optional freeform context string (hostname, snapshot timestamps, etc.)
            model:   Optional explicit model override ("provider/model" or "model").
                     Explicit overrides run without failover.
            access_token: The requesting user's bearer token, forwarded to the MCP
                     tool server so lookups are authorized as that user.
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

        async with AsyncExitStack() as stack:
            mcp, mcp_tools = await self._open_mcp(stack, access_token)
            tools = mcp_tools + [LOCAL_TOOLS[name] for name in ANALYSIS_LOCAL_TOOLS]

            chunk_count = 0
            async for chunk in self._run_tool_loop(
                "analysis", model, messages, tools, mcp, max_tokens=ANALYSIS_MAX_TOKENS
            ):
                chunk_count += 1
                yield chunk
            logger.info("[AI] analysis stream done, yielded %d chunks", chunk_count)

    async def ask(
        self,
        prompt: str,
        conversation_history: list[dict] = None,
        context: str | None = None,
        extra_system_prompts: list[str] | None = None,
        model: str | None = None,
        access_token: str | None = None,
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
            access_token: The requesting user's bearer token, forwarded to the MCP
                   tool server so lookups are authorized as that user.
        """
        if conversation_history is None:
            conversation_history = []

        extra_messages = [{"role": "system", "content": p} for p in (extra_system_prompts or [])]
        context_messages = [{"role": "system", "content": f"Page context:\n{context}"}] if context else []

        try:
            async with AsyncExitStack() as stack:
                # MCP is optional and may be unreachable — degrade to local
                # tools only rather than losing tool-calling entirely (see
                # LOCAL_TOOLS: those never depend on MCP being up).
                mcp, mcp_tools = await self._open_mcp(stack, access_token)
                tools = mcp_tools + [LOCAL_TOOLS[name] for name in CHAT_LOCAL_TOOLS]

                # Build message history: system + ui context + page context + history + current prompt
                messages = [
                    *self.system_messages,
                    *extra_messages,
                    *context_messages,
                    *conversation_history,
                    {"role": "user", "content": prompt},
                ]

                async for chunk in self._run_tool_loop("chat", model, messages, tools, mcp, max_tokens=CHAT_MAX_TOKENS):
                    yield chunk

        except (AllLevelsExhaustedError, APIStatusError):
            raise
        except Exception as exc:
            # Last-resort fallback for anything unexpected above — MCP itself
            # already degrades gracefully inline (see _open_mcp) so this is
            # no longer MCP-specific, just a safety net.
            logger.warning("[AI] ask() failed unexpectedly, falling back to no-tools chat: %s", exc)
            messages = [
                *self.system_messages,
                *extra_messages,
                *context_messages,
                *conversation_history,
                {"role": "user", "content": prompt},
            ]
            async for chunk in self._stream_with_failover("chat", model, messages=messages):
                if isinstance(chunk, UsageEvent):
                    yield chunk
                elif chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
