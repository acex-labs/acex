"""What the adapters built on the OpenAI SDK share: client, errors, listing."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from openai import APIConnectionError, APIError, APIStatusError, AsyncOpenAI

from ..errors import ProviderError
from ..types import ToolCall
from .base import ModelAdapter

#: Request fields a provider names when it refuses a feature rather than the
#: request as a whole. The router retries without the feature.
UNSUPPORTED_PARAMS = ("reasoning_effort", "reasoning", "reasoning.effort", "tools", "tool_choice")


class OpenAISDKAdapter(ModelAdapter):
    """Base for protocols served through the OpenAI SDK.

    `credential` is a static key, or an async callable the SDK calls before
    every request for a fresh bearer token.
    """

    def __init__(self, base_url: str, credential: str | Callable[[], Awaitable[str]]):
        self.client = AsyncOpenAI(api_key=credential, base_url=base_url)

    async def list_models(self) -> list[dict]:
        try:
            result = await self.client.models.list()
        except APIError as exc:
            raise self.error(exc) from exc
        return [model if isinstance(model, dict) else model.model_dump() for model in result.data]

    @staticmethod
    def error(exc: APIError) -> ProviderError:
        """Classify an SDK error (see ProviderError for what each kind means)."""
        if isinstance(exc, APIConnectionError):
            return ProviderError(str(exc), "transient")
        status = exc.status_code if isinstance(exc, APIStatusError) else None
        param = getattr(exc, "param", None)
        if status is None or status >= 500:
            kind = "transient"
        elif status == 429:
            kind = "rate_limit"
        elif status in (401, 403):
            kind = "auth"
        elif param in UNSUPPORTED_PARAMS:
            kind = "unsupported"
        else:
            kind = "invalid_request"
        return ProviderError(exc.message, kind, status, param)

    @staticmethod
    def tool_call(call_id: str, name: str, raw_arguments: Any) -> ToolCall:
        """A ToolCall from the arguments as the provider sent them.

        Some providers send a dict rather than the JSON string the spec asks
        for. Arguments that are not a JSON object leave `arguments` None, so the
        loop can tell the model instead of calling the tool with nothing.
        """
        raw = raw_arguments if isinstance(raw_arguments, str) else json.dumps(raw_arguments or {})
        try:
            arguments = json.loads(raw) if raw.strip() else {}
        except ValueError:
            arguments = None
        return ToolCall(call_id, name, arguments if isinstance(arguments, dict) else None, raw)

    @staticmethod
    def field(obj: Any, name: str) -> Any:
        """A field of an SDK object or a plain dict; providers return either for extras."""
        if obj is None:
            return None
        return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
