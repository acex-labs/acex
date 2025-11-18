import json
from openai import AsyncOpenAI
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from .settings import DEFAULT_SYSTEM_PROMPTS

class AIOpsManager:
    
    def __init__(self, api_key: str = None, base_url: str = None, mcp_server_url: str = "http://localhost:8000/mcp", system_prompt: str | list[str] = None):
        """
        Initialize AI Ops Manager with OpenAI client and MCP server.
        
        Args:
            api_key: API key for AI service
            base_url: Base URL for AI API
            mcp_server_url: URL to MCP server (default: http://localhost:8000/mcp)
            system_prompt: System prompt(s) for the AI assistant. Can be a string or list of strings.
        """
        print(f"Adding AI ops with API: {base_url} and MCP: {mcp_server_url}")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        transport = StreamableHttpTransport(url=mcp_server_url)
        self.mcp = Client(transport)
        
        # Convert system_prompt to list of message dicts
        if system_prompt is None:
            self.system_messages = [{"role": "system", "content": "You are a helpful network automation assistant with access to network configuration tools."}]
        elif isinstance(system_prompt, str):
            self.system_messages = [{"role": "system", "content": system_prompt}]
        else:
            self.system_messages = [{"role": "system", "content": msg} for msg in system_prompt]


    def _convert_tools(self, tool_list):
        """
        Convert FastMCP Tool objects → OpenAI function-call schema
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": getattr(t, "description", "") or "",
                    "parameters": getattr(t, "parameters", {"type": "object", "properties": {}})
                }
            }
            for t in tool_list
        ]

    async def call_mcp_tool(self, tool_name: str, args=None):
        """
        Execute MCP tool using streaming JSON-RPC
        """
        if args is None:
            args = {}
        result = await self.mcp.call_tool(tool_name, arguments=args)
        return result
    

    async def ask(self, prompt: str, conversation_history: list[dict] = None):
        """Stream AI response with tool calling support and conversation history
        
        Args:
            prompt: The user's current question/prompt
            conversation_history: Previous messages in the conversation
                                 Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        if conversation_history is None:
            conversation_history = []
            
        async with self.mcp:
            raw_tools = await self.mcp.list_tools()
            tools = self._convert_tools(raw_tools)

            # Build message history: system + history + current prompt
            messages = [
                *self.system_messages,
                *conversation_history,
                {"role": "user", "content": prompt}
            ]

            # First request - check if tools are needed
            response = await self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )

            msg = response.choices[0].message

            # Handle tool calls if present
            if msg.tool_calls:
                # Collect all tool results first
                tool_messages = []
                
                for call in msg.tool_calls:
                    args = call.function.arguments or {}
                    if isinstance(args, str):
                        args = json.loads(args)

                    yield f"[Calling tool: {call.function.name}]\n"

                    try:
                        mcp_result = await self.call_mcp_tool(call.function.name, args)
                        texts = []
                        for c in mcp_result.content:
                            if hasattr(c, "text"):
                                texts.append(c.text)

                        tool_output_text = "".join(texts).strip()
                        try:
                            tool_output = json.loads(tool_output_text)
                        except json.JSONDecodeError:
                            tool_output = tool_output_text
                        
                        # Add tool result to messages
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.function.name,
                            "content": json.dumps(tool_output)
                        })
                    except Exception as e:
                        yield f"[Error calling {call.function.name}: {str(e)}]\n"
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "name": call.function.name,
                            "content": json.dumps({"error": str(e)})
                        })

                # Now make a single LLM call with all tool results
                # Build final messages with tool results
                final_messages = [
                    *messages,  # Include full conversation history (system + history + user prompt)
                ]
                
                # Add assistant message with tool calls
                final_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments if isinstance(call.function.arguments, str) else json.dumps(call.function.arguments)
                            }
                        }
                        for call in msg.tool_calls
                    ]
                })
                
                # Add all tool results
                final_messages.extend(tool_messages)
                
                # Debug: log the final message structure
                import sys
                print(f"[DEBUG] Final messages count: {len(final_messages)}", file=sys.stderr)
                print(f"[DEBUG] Last message: {json.dumps(final_messages[-1], indent=2)}", file=sys.stderr)
                
                try:
                    stream = await self.client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=final_messages,
                        stream=True
                    )
                    
                    async for chunk in stream:
                        if chunk.choices:
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'reasoning') and delta.reasoning:
                                yield f"[Reasoning: {delta.reasoning}]\n"
                            if delta.content:
                                yield delta.content
                except Exception as e:
                    yield f"\n[Error in LLM stream: {str(e)}]\n"
                    import traceback
                    yield f"[Traceback: {traceback.format_exc()}]\n"
            else:
                # No tools needed - stream initial response
                stream = await self.client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    stream=True
                )
                
                async for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'reasoning') and delta.reasoning:
                            yield f"[Reasoning: {delta.reasoning}]\n"
                        if delta.content:
                            yield delta.content
