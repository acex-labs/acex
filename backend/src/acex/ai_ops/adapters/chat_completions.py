"""POST /chat/completions — what OpenAI-compatible servers speak."""

import json
from collections.abc import AsyncIterator

from openai import APIError

from ..types import AssistantRound, ConversationItem, Message, StreamEvent, TextDelta, Turn, Usage
from .openai_sdk import OpenAISDKAdapter


class ChatCompletionsAdapter(OpenAISDKAdapter):
    async def stream(self, turn: Turn) -> AsyncIterator[StreamEvent]:
        # Tool calls stream in fragments keyed by index: the id and name come
        # first, the JSON arguments in pieces after.
        calls: dict[int, dict] = {}
        usage = None
        try:
            stream = await self.client.chat.completions.create(**self.request(turn))
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = self.usage(chunk.usage)
                for choice in chunk.choices or []:
                    # Azure sends choices without a delta, e.g. for content-filter results.
                    delta = choice.delta
                    if delta is None:
                        continue
                    if delta.content:
                        yield TextDelta(delta.content)
                    for part in delta.tool_calls or []:
                        call = calls.setdefault(
                            part.index if part.index is not None else len(calls),
                            {"id": "", "name": "", "arguments": ""},
                        )
                        call["id"] = part.id or call["id"]
                        if part.function is not None:
                            call["name"] = call["name"] or part.function.name or ""
                            arguments = part.function.arguments
                            if isinstance(arguments, dict):
                                arguments = json.dumps(arguments)
                            call["arguments"] += arguments or ""
        except APIError as exc:
            raise self.error(exc) from exc

        for index, call in sorted(calls.items()):
            yield self.tool_call(call["id"] or f"call_{index}", call["name"], call["arguments"])
        if usage is not None:
            yield usage

    def request(self, turn: Turn) -> dict:
        request = {
            "model": turn.model,
            "messages": self.messages(turn.conversation),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if turn.tools:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in turn.tools
            ]
            request["tool_choice"] = turn.tool_choice
        # Only sent when there is a limit: the SDK serializes None as
        # `"max_tokens": null`, which strict providers reject.
        if turn.max_tokens is not None:
            request["max_tokens"] = turn.max_tokens
        if turn.reasoning_effort is not None:
            request["reasoning_effort"] = turn.reasoning_effort
        return {**request, **turn.params}

    @staticmethod
    def messages(conversation: list[ConversationItem]) -> list[dict]:
        messages = []
        for item in conversation:
            if isinstance(item, Message):
                messages.append({"role": item.role, "content": item.text})
            elif isinstance(item, AssistantRound):
                message = {"role": "assistant", "content": item.text or None}
                if item.tool_calls:
                    message["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments or {})},
                        }
                        for call in item.tool_calls
                    ]
                messages.append(message)
            else:
                messages.append(
                    {"role": "tool", "tool_call_id": item.call_id, "name": item.name, "content": item.output}
                )
        return messages

    def usage(self, usage) -> Usage:
        # Berget reports reasoning_tokens and co2_grams at the top level;
        # OpenAI nests reasoning under completion_tokens_details.
        reasoning = self.field(usage, "reasoning_tokens")
        if reasoning is None:
            reasoning = self.field(self.field(usage, "completion_tokens_details"), "reasoning_tokens")
        return Usage(
            prompt_tokens=self.field(usage, "prompt_tokens") or 0,
            completion_tokens=self.field(usage, "completion_tokens") or 0,
            reasoning_tokens=reasoning,
            cached_tokens=self.field(self.field(usage, "prompt_tokens_details"), "cached_tokens"),
            co2_grams=self.field(usage, "co2_grams"),
        )
