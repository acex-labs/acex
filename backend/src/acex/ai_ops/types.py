"""The conversation format between the tool loop and the model adapters.

The tool loop only ever handles these types; each adapter translates them to
and from its wire protocol. That keeps protocol differences — message shapes,
tool schemas, streaming events, usage fields — out of the loop, so a provider
is a choice of adapter rather than a special case in the loop.
"""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class ToolSpec:
    """A tool offered to the model. `parameters` is a JSON schema."""

    name: str
    description: str
    parameters: dict


@dataclass(slots=True)
class ToolCall:
    """A tool call the model made.

    `arguments` is None when the model sent arguments that are not a JSON
    object; `raw_arguments` is what it sent either way.
    """

    id: str
    name: str
    arguments: dict | None
    raw_arguments: str = ""


@dataclass(slots=True)
class Message:
    """Plain text from the system, the user, or an earlier assistant turn."""

    role: Literal["system", "user", "assistant"]
    text: str


@dataclass(slots=True)
class AssistantRound:
    """What the model produced in one round of the tool loop.

    `state` is opaque to the loop: an adapter attaches whatever its protocol
    needs to have sent back in the next round (the Responses API's reasoning
    items, for example) and gets it back unchanged.
    """

    text: str
    tool_calls: list[ToolCall]
    state: Any = None


@dataclass(slots=True)
class ToolResult:
    """The output of one tool call, as text the model reads."""

    call_id: str
    name: str
    output: str


ConversationItem = Message | AssistantRound | ToolResult


@dataclass(slots=True)
class Turn:
    """One request to a model: the conversation so far plus how to answer."""

    model: str
    conversation: list[ConversationItem]
    tools: list[ToolSpec] = field(default_factory=list)
    #: "auto" lets the model call tools; "none" makes it answer in text.
    tool_choice: Literal["auto", "none"] = "auto"
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    #: Extra request fields, sent as they are.
    params: dict = field(default_factory=dict)


@dataclass(slots=True)
class TextDelta:
    """A piece of the answer, streamed as it is generated."""

    text: str


@dataclass(slots=True)
class RoundState:
    """Adapter state for the round, emitted once before the stream ends."""

    data: Any


@dataclass(slots=True)
class Usage:
    """Token counts reported by the provider, summed over a request's rounds."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    co2_grams: float | None = None

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        for name in ("reasoning_tokens", "cached_tokens", "co2_grams"):
            value = getattr(other, name)
            if value is not None:
                setattr(self, name, (getattr(self, name) or 0) + value)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


StreamEvent = TextDelta | ToolCall | RoundState | Usage
