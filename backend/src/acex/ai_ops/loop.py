"""The agentic tool loop: let the model call tools, read the results and call
more before answering, streaming every round as it is generated."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .catalog import ModelCatalog
from .events import UsageEvent
from .router import ModelSession
from .tools import Toolbox
from .types import (
    AssistantRound,
    ConversationItem,
    Message,
    RoundState,
    TextDelta,
    ToolCall,
    ToolResult,
    Turn,
    Usage,
)

logger = logging.getLogger("acex.ai_ops")

#: Sent when a model wrote its tool call into the text instead of making it.
TOOL_CALL_AS_TEXT = (
    "That tool call was written as text, so it did not run and produced no result. "
    "Call the tool through the function-calling interface instead."
)

#: Closes the tool-calling phase once the rounds run out. Without being told the
#: turn is over, a model reads the absence of tools as "write the call yourself".
FINAL_ANSWER_NUDGE = (
    "You now have the tool results. Answer the question in prose, based on what those results "
    "actually show. The tool-calling phase is over — do not call or write any further tool calls. "
    "If something you wanted to check is still unknown, say so plainly instead of trying again."
)

#: Used when a closing attempt produced no text at all.
FINAL_ANSWER_RETRY = (
    "You produced no answer. Write it now, in plain prose, using only the tool results already "
    "in this conversation. Do not write tool-call syntax of any kind."
)

#: Better an honest sentence than an empty reply that reads as a crash.
NO_ANSWER = (
    "I gathered the information but couldn't turn it into an answer. "
    "The tool results above are what I found — ask again and I'll try to summarise them."
)


class ToolSyntaxFilter:
    """Keeps tool-call syntax a model wrote as text out of the answer.

    Some models write their native call syntax into the content when the
    provider did not turn it into a structured call. Everything from the
    marker on is dropped. The marker can straddle two streamed pieces, so
    trailing text that could still become it is held until the next piece.
    """

    MARKER = "<tool_call"

    def __init__(self):
        self.buffer = ""
        self.suppressed = False

    def feed(self, text: str) -> str:
        """The part of the text that is safe to show now."""
        if self.suppressed:
            return ""
        self.buffer += text
        at = self.buffer.find(self.MARKER)
        if at >= 0:
            self.suppressed = True
            emit, self.buffer = self.buffer[:at], ""
            return emit
        emit, self.buffer = self.hold(self.buffer)
        return emit

    def flush(self) -> str:
        rest, self.buffer = ("" if self.suppressed else self.buffer), ""
        return rest

    @classmethod
    def hold(cls, buffer: str) -> tuple[str, str]:
        """Split a buffer into (safe to emit, hold back)."""
        for length in range(len(cls.MARKER) - 1, 0, -1):
            if buffer.endswith(cls.MARKER[:length]):
                return buffer[:-length], buffer[-length:]
        return buffer, ""


@dataclass(slots=True)
class RoundResult:
    """What one round produced. `text` is what the user saw, `raw` all of it."""

    text: str = ""
    raw: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    state: Any = None
    suppressed: bool = False


class ToolLoop:
    """Runs one request: rounds until the model answers in text, at most
    max_rounds of them, then a closing round that has to answer.

    Yields the answer text as it streams, the toolbox's UI events, and one
    UsageEvent at the end when the provider reported usage. Mutates the
    conversation it is given.
    """

    def __init__(
        self,
        session: ModelSession,
        catalog: ModelCatalog,
        toolbox: Toolbox,
        max_rounds: int = 5,
        max_tokens: int | None = None,
    ):
        self.session = session
        self.catalog = catalog
        self.toolbox = toolbox
        self.max_rounds = max_rounds
        self.max_tokens = max_tokens
        self.usage = Usage()
        self.usage_reported = False
        self.started_at = time.monotonic()
        self.first_output_at: float | None = None
        self.answered = False

    async def run(self, conversation: list[ConversationItem]):
        corrections = 0
        used_tools = False
        for _ in range(self.max_rounds):
            result = RoundResult()
            async for piece in self._round(conversation, "auto", result):
                yield piece

            if not result.tool_calls:
                if result.suppressed and corrections < 1:
                    corrections += 1
                    logger.warning(f"[AI] model wrote a tool call as text for task '{self.session.task}'; asking again")
                    conversation.append(AssistantRound(result.raw, []))
                    conversation.append(Message("user", TOOL_CALL_AS_TEXT))
                    continue
                if result.text.strip():
                    if usage := self.usage_event():
                        yield usage
                    return
                break

            used_tools = True
            conversation.append(AssistantRound(result.raw, result.tool_calls, result.state))
            for call in result.tool_calls:
                async for item in self.toolbox.run(call):
                    if isinstance(item, ToolResult):
                        conversation.append(item)
                    else:
                        yield item

        # The model is told this is the closing turn; tools stay declared so it
        # keeps their context, but tool_choice "none" makes it answer.
        if used_tools:
            conversation.append(Message("user", FINAL_ANSWER_NUDGE))
        for attempt in range(2):
            result = RoundResult()
            async for piece in self._round(conversation, "none", result):
                yield piece
            if result.text.strip():
                break
            logger.warning(f"[AI] empty answer for task '{self.session.task}' (attempt {attempt + 1})")
            if result.raw:
                conversation.append(AssistantRound(result.raw, []))
            conversation.append(Message("user", FINAL_ANSWER_RETRY))
        else:
            yield NO_ANSWER
        if usage := self.usage_event():
            yield usage

    async def _round(self, conversation: list[ConversationItem], tool_choice: str, result: RoundResult):
        """Stream one round into `result`, yielding the text the user should see."""
        turn = Turn(
            model="",
            conversation=conversation,
            tools=self.toolbox.specs,
            tool_choice=tool_choice,
            max_tokens=self.max_tokens,
        )
        syntax = ToolSyntaxFilter()
        async for event in self.session.stream(turn):
            if self.first_output_at is None:
                self.first_output_at = time.monotonic()
            if isinstance(event, TextDelta):
                result.raw += event.text
                text = syntax.feed(event.text)
                if text:
                    yield self._text(text, result)
            elif isinstance(event, ToolCall):
                result.tool_calls.append(event)
            elif isinstance(event, RoundState):
                result.state = event.data
            else:
                self.usage.add(event)
                self.usage_reported = True
        text = syntax.flush()
        if text:
            yield self._text(text, result)
        result.suppressed = syntax.suppressed
        if result.suppressed:
            logger.warning(f"[AI] suppressed tool-call syntax from the answer for task '{self.session.task}'")

    def _text(self, text: str, result: RoundResult) -> str:
        """Text for the user; a round's first text is set apart from an earlier round's."""
        if not result.text and self.answered:
            text = "\n\n" + text
        result.text += text
        self.answered = True
        return text

    def usage_event(self) -> UsageEvent | None:
        """Usage summed over the request's rounds, with cost and throughput.

        tokens_per_second covers generation (first output → end), which is the
        number users perceive as speed.
        """
        if not self.usage_reported or self.session.target is None:
            return None
        level = self.session.target.level
        now = time.monotonic()
        generating = now - (self.first_output_at or self.started_at)
        cost, currency = self.catalog.cost(level.provider, level.model, self.usage)
        return UsageEvent(
            {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
                "reasoning_tokens": self.usage.reasoning_tokens,
                "cached_tokens": self.usage.cached_tokens,
                "co2_grams": self.usage.co2_grams,
                "provider": level.provider,
                "model": level.model,
                "cost": cost,
                "currency": currency,
                "elapsed_seconds": round(now - self.started_at, 2),
                "tokens_per_second": (
                    round(self.usage.completion_tokens / generating, 1)
                    if self.usage.completion_tokens and generating > 0
                    else None
                ),
            }
        )
