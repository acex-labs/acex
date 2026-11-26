"""POST /responses — OpenAI's newer API.

The only protocol on which OpenAI and Azure reasoning models accept tools. The
model's reasoning comes back as output items of its own; sending them back in
the next round lets the model carry on reasoning after a tool result instead
of starting over. With store=False nothing is kept server-side, so the items
carry their reasoning encrypted (include=reasoning.encrypted_content).
"""

import json
from collections.abc import AsyncIterator

from openai import APIError

from ..errors import ProviderError
from ..types import AssistantRound, ConversationItem, Message, RoundState, StreamEvent, TextDelta, Turn, Usage
from .openai_sdk import OpenAISDKAdapter


class ResponsesAdapter(OpenAISDKAdapter):
    async def stream(self, turn: Turn) -> AsyncIterator[StreamEvent]:
        # Every output item exactly as received; sent back verbatim next round,
        # which keeps reasoning items paired with the items that followed them.
        items: list[dict] = []
        usage = None
        try:
            stream = await self.client.responses.create(**self.request(turn))
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield TextDelta(event.delta)
                elif event.type == "response.output_item.done":
                    items.append(event.item.model_dump(mode="json", exclude_none=True))
                    if event.item.type == "function_call":
                        yield self.tool_call(event.item.call_id, event.item.name, event.item.arguments)
                elif event.type in ("response.completed", "response.incomplete"):
                    if event.response.usage is not None:
                        usage = self.usage(event.response.usage)
                elif event.type == "response.failed":
                    raise self.failure(self.field(event.response, "error"))
                elif event.type == "error":
                    raise self.failure(event)
        except APIError as exc:
            raise self.error(exc) from exc

        yield RoundState(items)
        if usage is not None:
            yield usage

    def request(self, turn: Turn) -> dict:
        request = {
            "model": turn.model,
            "input": self.input(turn.conversation),
            "stream": True,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if turn.tools:
            # strict defaults to true here, which only accepts schemas that
            # list every property as required — MCP tool schemas do not.
            request["tools"] = [
                {
                    "type": "function",
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                    "strict": False,
                }
                for t in turn.tools
            ]
            request["tool_choice"] = turn.tool_choice
        if turn.max_tokens is not None:
            request["max_output_tokens"] = turn.max_tokens
        if turn.reasoning_effort is not None:
            request["reasoning"] = {"effort": turn.reasoning_effort}
        return {**request, **turn.params}

    @staticmethod
    def input(conversation: list[ConversationItem]) -> list[dict]:
        items = []
        for item in conversation:
            if isinstance(item, Message):
                items.append({"role": item.role, "content": item.text})
            elif isinstance(item, AssistantRound):
                if item.state is not None:
                    items.extend(item.state)
                    continue
                # A round from another adapter, e.g. before a failover.
                if item.text:
                    items.append({"role": "assistant", "content": item.text})
                items.extend(
                    {
                        "type": "function_call",
                        "call_id": call.id,
                        "name": call.name,
                        "arguments": json.dumps(call.arguments or {}),
                    }
                    for call in item.tool_calls
                )
            else:
                items.append({"type": "function_call_output", "call_id": item.call_id, "output": item.output})
        return items

    def usage(self, usage) -> Usage:
        return Usage(
            prompt_tokens=self.field(usage, "input_tokens") or 0,
            completion_tokens=self.field(usage, "output_tokens") or 0,
            reasoning_tokens=self.field(self.field(usage, "output_tokens_details"), "reasoning_tokens"),
            cached_tokens=self.field(self.field(usage, "input_tokens_details"), "cached_tokens"),
        )

    def failure(self, error) -> ProviderError:
        """A failure reported inside the stream rather than as an HTTP status."""
        code = self.field(error, "code")
        message = self.field(error, "message") or "response failed"
        if code == "rate_limit_exceeded":
            return ProviderError(message, "rate_limit")
        if code in ("server_error", None):
            return ProviderError(message, "transient")
        return ProviderError(message, "invalid_request", param=self.field(error, "param"))
