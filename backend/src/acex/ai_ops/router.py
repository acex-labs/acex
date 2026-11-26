"""Which model answers a request, with which settings, and what happens when it fails."""

import dataclasses
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from .adapters import ModelAdapter
from .catalog import ModelCatalog
from .config import AIChainLevel, AIOpsSettings
from .endpoints import Endpoints
from .errors import AllLevelsExhaustedError, ProviderError
from .types import StreamEvent, Turn

logger = logging.getLogger("acex.ai_ops")

#: Request fields that turn reasoning on or off, as providers name them in errors.
REASONING_PARAMS = ("reasoning_effort", "reasoning", "reasoning.effort")

#: Ways a model's requests are cut down after it refused a feature.
REASONING_OFF = "reasoning_off"
NO_TOOLS = "no_tools"


@dataclass(slots=True)
class Target:
    """A chain level resolved to the adapter that serves it."""

    level: AIChainLevel
    adapter: ModelAdapter


class ModelRouter:
    """Turns a task into the models to try and runs rounds against them.

    Settings are layered, later winning: the model's configuration, then the
    chain level's, then the request's own. Tools are left out for a model
    known not to support them.

    When a model refuses a feature (ProviderError kind "unsupported"), the same
    model is asked again without it rather than failing the request: first
    with reasoning turned off, then without tools. What worked is remembered
    per model for the life of the process, so only the first request pays for
    the retries.
    """

    def __init__(self, settings: AIOpsSettings, endpoints: Endpoints, catalog: ModelCatalog):
        self.settings = settings
        self.endpoints = endpoints
        self.catalog = catalog
        self._degraded: dict[tuple[str, str], frozenset[str]] = {}

    def session(self, task: str, model_override: str | None = None) -> "ModelSession":
        return ModelSession(self, task, self.resolve(task, model_override), pinned=model_override is not None)

    def resolve(self, task: str, model_override: str | None = None) -> list[Target]:
        """The levels to try, in order.

        An explicit override is a single level: the model in the provider it
        names ("provider/model"), or in the first chain level's provider.
        """
        chain = self.settings.chain_for(task)
        if model_override:
            provider, model = (
                model_override.split("/", 1) if "/" in model_override else (chain[0].provider, model_override)
            )
            chain = [AIChainLevel(provider=provider, model=model)]
        return [
            Target(level, self.endpoints.adapter(self.settings.provider_for(level), level.model)) for level in chain
        ]

    async def stream(self, target: Target, turn: Turn) -> AsyncIterator[StreamEvent]:
        """One round against one model, cut down as far as the model needs."""
        key = (target.level.provider, target.level.model)
        degraded = self._degraded.get(key, frozenset())
        while True:
            request = self._request(target, turn, degraded)
            events = target.adapter.stream(request)
            try:
                first = await anext(events)
            except StopAsyncIteration:
                return
            except ProviderError as exc:
                if exc.kind != "unsupported" or (degraded := self._degrade(degraded, request, exc)) is None:
                    raise
                logger.warning(
                    f"[AI] {target.level.label} refused part of the request ({exc}); "
                    f"retrying with {', '.join(sorted(degraded))} from now on"
                )
                self._degraded[key] = degraded
                continue
            yield first
            async for event in events:
                yield event
            return

    def _request(self, target: Target, turn: Turn, degraded: frozenset[str]) -> Turn:
        level = target.level
        config = self.settings.provider_for(level).model(level.model)
        tools = turn.tools
        if NO_TOOLS in degraded or self.catalog.entry(level.provider, level.model)["supports_tools"] is False:
            tools = []
        return dataclasses.replace(
            turn,
            model=level.model,
            tools=tools,
            reasoning_effort=(
                "none"
                if REASONING_OFF in degraded
                else turn.reasoning_effort or level.reasoning_effort or config.reasoning_effort
            ),
            params={**config.params, **level.params, **turn.params},
        )

    @staticmethod
    def _degrade(degraded: frozenset[str], request: Turn, exc: ProviderError) -> frozenset[str] | None:
        """The next cut-down after a refusal, or None when nothing is left to drop.

        Reasoning off goes first because it keeps the tools. If the model then
        refuses that too (some reasoning models cannot turn it off), reasoning
        goes back to its setting and the tools go instead.
        """
        if exc.param in REASONING_PARAMS and REASONING_OFF not in degraded and request.reasoning_effort != "none":
            return degraded | {REASONING_OFF}
        if request.tools and NO_TOOLS not in degraded:
            return (degraded - {REASONING_OFF}) | {NO_TOOLS}
        return None


class ModelSession:
    """The model one request talks to.

    The first round fails over along the chain until a level produces output;
    from then on the request stays on that level, since the conversation
    (tool calls, reasoning state) is tied to it. An explicit model override is
    pinned from the start and never fails over.
    """

    def __init__(self, router: ModelRouter, task: str, candidates: list[Target], pinned: bool):
        self.router = router
        self.task = task
        self.candidates = candidates
        self.pinned = pinned
        self.target: Target | None = None

    async def stream(self, turn: Turn) -> AsyncIterator[StreamEvent]:
        if self.target is not None:
            async for event in self.router.stream(self.target, turn):
                yield event
            return

        failures: list[tuple[str, str]] = []
        for target in self.candidates:
            events = self.router.stream(target, turn)
            try:
                first = await anext(events)
            except StopAsyncIteration:
                self.target = target
                return
            except ProviderError as exc:
                if self.pinned or not exc.failover:
                    raise
                logger.warning(f"[AI] level {target.level.label} failed for task '{self.task}': {exc}")
                failures.append((target.level.label, str(exc)))
                continue
            if failures:
                logger.warning(f"[AI] failover: using {target.level.label} for task '{self.task}'")
            self.target = target
            yield first
            async for event in events:
                yield event
            return
        raise AllLevelsExhaustedError(self.task, failures)
