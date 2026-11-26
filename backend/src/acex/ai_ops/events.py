"""Events the AI Ops streams yield next to the answer text.

Everything that is not the assistant's prose arrives as one of these, so the
API layer can send it as a typed SSE event and the UI can render it as its own
element instead of finding it spliced into the text.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class UsageEvent:
    """Provider-reported token usage for one request, summed over its rounds.

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
    """Progress of one tool call. status is "running", then "ok" or "error"."""

    name: str
    status: str
    error: str | None = None


@dataclass(slots=True)
class NavigateEvent:
    """A page the assistant suggests opening.

    The frontend renders it as a link the user must click — navigation is
    never automatic.
    """

    data: dict
