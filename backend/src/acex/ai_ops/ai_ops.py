"""AI Ops: the chat and config-analysis tasks, on top of the provider layer.

AIOpsManager   tasks, prompts, MCP session
  ToolLoop     rounds, tool calls, UI events          (loop.py)
    ModelRouter  chains, failover, settings, cut-downs (router.py)
      adapter    one wire protocol to one endpoint     (adapters/)
"""

import logging
from contextlib import AsyncExitStack

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from .catalog import ModelCatalog
from .config import AIOpsSettings
from .endpoints import Endpoints
from .errors import AllLevelsExhaustedError, ProviderError
from .events import NavigateEvent, PlanEvent, ToolCallEvent, UsageEvent
from .loop import ToolLoop
from .router import ModelRouter
from .settings import (
    ANALYSIS_MAX_TOKENS,
    CHAT_MAX_TOKENS,
    CONFIG_ANALYSIS_SYSTEM_PROMPT,
    CONFIG_ANALYSIS_TASK_PROMPTS,
)
from .tools import ANALYSIS_LOCAL_TOOLS, CHAT_LOCAL_TOOLS, Toolbox
from .types import ConversationItem, Message

logger = logging.getLogger("acex.ai_ops")

__all__ = [
    "AIOpsManager",
    "AllLevelsExhaustedError",
    "NavigateEvent",
    "PlanEvent",
    "ProviderError",
    "ToolCallEvent",
    "UsageEvent",
]

DEFAULT_SYSTEM_PROMPT = "You are a helpful network automation assistant with access to network configuration tools."


class AIOpsManager:
    def __init__(self, settings: AIOpsSettings, system_prompt: str | list[str] | None = None):
        """
        Args:
            settings: Providers, models and per-task failover chains (see acex.settings.ai_ops).
            system_prompt: System prompt(s) for the chat assistant.
        """
        self.settings = settings
        self.endpoints = Endpoints(settings)
        self.catalog = ModelCatalog(settings, self.endpoints)
        self.router = ModelRouter(settings, self.endpoints, self.catalog)

        if settings.mcp_server_url is None:
            logger.info("[AI] no MCP server url configured — starting with local tools only")

        prompts = [system_prompt or DEFAULT_SYSTEM_PROMPT] if not isinstance(system_prompt, list) else system_prompt
        self.system_messages = [Message("system", prompt) for prompt in prompts]

    # ------------------------------------------------------------------
    # Providers and models
    # ------------------------------------------------------------------

    async def list_models(self, provider_name: str, force_refresh: bool = False, include_all: bool = False):
        """A provider's models with metadata; see ModelCatalog.models."""
        return await self.catalog.models(provider_name, force_refresh=force_refresh, include_all=include_all)

    def providers_info(self) -> list[dict]:
        """Configured providers; the API layer adds models and health via list_models()."""
        return [
            {"name": p.name, "base_url": p.base_url, "api": p.api, "has_static_models": bool(p.models)}
            for p in self.settings.providers.values()
        ]

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def ask(
        self,
        prompt: str,
        conversation_history: list[dict] | None = None,
        context: str | None = None,
        extra_system_prompts: list[str] | None = None,
        model: str | None = None,
        access_token: str | None = None,
    ):
        """Stream a chat answer, with tool calling and conversation history.

        Args:
            prompt: The user's current question.
            conversation_history: Earlier turns, [{"role": "user"|"assistant", "content": "..."}].
            context: Page context (visible data), injected as a system message.
            extra_system_prompts: Added after the base prompts (the web UI's schema, skills, rules).
            model: Explicit model ("provider/model" or "model"); runs without failover.
            access_token: The requesting user's bearer token, forwarded to the MCP
                tool server so lookups are authorized as that user.
        """
        conversation: list[ConversationItem] = [
            *self.system_messages,
            *(Message("system", p) for p in extra_system_prompts or []),
            *([Message("system", f"Page context:\n{context}")] if context else []),
            *(
                Message(m["role"], m.get("content") or "")
                for m in conversation_history or []
                if m.get("role") in ("user", "assistant")
            ),
            Message("user", prompt),
        ]
        async for chunk in self._run("chat", model, conversation, CHAT_LOCAL_TOOLS, access_token, CHAT_MAX_TOKENS):
            yield chunk

    async def analyze_config_diff(
        self,
        task: str,
        diff: str,
        context: str = "",
        model: str | None = None,
        access_token: str | None = None,
    ):
        """Stream a focused config-diff analysis.

        Has MCP tool access (LLDP neighbours, node configs) so it can verify a
        claim — like whether a downstream device still needs a VLAN being
        removed — against real data instead of only reasoning from the diff.
        Offers `plan` but not `navigate_to`, which is a web-UI concern.

        Args:
            task:    One of 'explain', 'risk_assessment', 'alignment'.
            diff:    Unified diff text (the config change to analyse).
            context: Optional freeform context (hostname, snapshot timestamps, ...).
            model:   Explicit model ("provider/model" or "model"); runs without failover.
            access_token: The requesting user's bearer token, forwarded to MCP.
        """
        template = CONFIG_ANALYSIS_TASK_PROMPTS.get(task)
        if template is None:
            raise ValueError(f"Unknown analysis task '{task}'. Valid tasks: {list(CONFIG_ANALYSIS_TASK_PROMPTS)}")
        conversation: list[ConversationItem] = [
            Message("system", CONFIG_ANALYSIS_SYSTEM_PROMPT),
            Message("user", template.format(diff=diff, context=f"{context}\n" if context else "")),
        ]
        logger.info(f"[AI] analyze_config_diff: task={task} diff_len={len(diff)}")
        async for chunk in self._run(
            "analysis", model, conversation, ANALYSIS_LOCAL_TOOLS, access_token, ANALYSIS_MAX_TOKENS
        ):
            yield chunk

    async def _run(
        self,
        task: str,
        model: str | None,
        conversation: list[ConversationItem],
        local_tools: tuple[str, ...],
        access_token: str | None,
        max_tokens: int | None,
    ):
        async with AsyncExitStack() as stack:
            mcp, mcp_tools = await self._open_mcp(stack, access_token)
            loop = ToolLoop(
                self.router.session(task, model),
                self.catalog,
                Toolbox(local_tools, mcp, mcp_tools),
                max_tokens=max_tokens,
            )
            async for chunk in loop.run(conversation):
                yield chunk

    # ------------------------------------------------------------------
    # MCP
    # ------------------------------------------------------------------

    def _mcp_client(self, access_token: str | None) -> Client | None:
        """An MCP client that acts as the caller.

        Built per request on purpose: transport headers are fixed at
        construction, so a shared client would send whichever user's token was
        set last to every concurrent user. The MCP server holds no credentials;
        it forwards this token to the ACE-X API, which authorizes the read.
        """
        if self.settings.mcp_server_url is None:
            return None
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        return Client(StreamableHttpTransport(url=self.settings.mcp_server_url, headers=headers))

    async def _open_mcp(self, stack: AsyncExitStack, access_token: str | None):
        """Enter an MCP session for this request: (client, tools).

        Both are empty when MCP is unconfigured or unreachable — the request
        then runs with the local tools rather than failing.
        """
        mcp = self._mcp_client(access_token)
        if mcp is None:
            return None, []
        try:
            await stack.enter_async_context(mcp)
            return mcp, await mcp.list_tools()
        except Exception as exc:
            logger.warning(f"[AI] MCP unavailable, continuing without its tools: {exc}")
            return None, []
