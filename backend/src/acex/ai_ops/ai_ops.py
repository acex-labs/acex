import json
from openai import OpenAI
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

class AIOpsManager:
    
    def __init__(self, api_key: str = None, base_url: str = None, mcp_server_url: str = "http://localhost:8000/mcp"):
        """
        Initialize AI Ops Manager with OpenAI client and MCP server.
        
        Args:
            api_key: API key for AI service
            base_url: Base URL for AI API
            mcp_server_url: URL to MCP server (default: http://localhost:8000/mcp)
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)

        transport = StreamableHttpTransport(url=mcp_server_url)
        self.mcp = Client(transport)


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
    

    async def ask(self, prompt: str) -> str:
        async with self.mcp:
            raw_tools = await self.mcp.list_tools()
            tools = self._convert_tools(raw_tools)

            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                tools=tools,
                tool_choice="auto"
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                for call in msg.tool_calls:
                    args = call.function.arguments or {}
                    if isinstance(args, str):
                        args = json.loads(args)

                    print(f"argument till func call: {args}")

                    mcp_result = await self.call_mcp_tool(call.function.name, args)
                    # mcp_result.content är lista av TextContent
                    texts = []
                    for c in mcp_result.content:
                        if hasattr(c, "text"):
                            texts.append(c.text)

                    tool_output_text = "".join(texts).strip()
                    try:
                        tool_output = json.loads(tool_output_text)
                    except json.JSONDecodeError:
                        tool_output = tool_output_text
                    print(tool_output)

                    print(tool_output, type(tool_output))

                    follow = self.client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[
                            {
                                "role": "assistant",
                                "content": "",
                                "function_call": {
                                    "name": call.function.name,
                                    "arguments": json.dumps(call.function.arguments or {})
                                }
                            },
                            {
                                "role": "tool",
                                "name": call.function.name,
                                "content": json.dumps(tool_output)  # här är det alltid str eller dict/list
                            }
                        ]
                    )
                    return follow.choices[0].message.content

            return str(msg.content)
