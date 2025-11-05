"""ACE-X MCP Server main entry point."""

from fastmcp import FastMCP

mcp = FastMCP("Acex-MCP")

@mcp.tool
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)