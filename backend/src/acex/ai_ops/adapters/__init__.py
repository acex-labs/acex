"""Model adapters, one per wire protocol, keyed by the `api` a provider names."""

from .base import ModelAdapter
from .chat_completions import ChatCompletionsAdapter
from .responses import ResponsesAdapter

ADAPTERS: dict[str, type[ModelAdapter]] = {
    "chat_completions": ChatCompletionsAdapter,
    "responses": ResponsesAdapter,
}

__all__ = ["ADAPTERS", "ChatCompletionsAdapter", "ModelAdapter", "ResponsesAdapter"]
