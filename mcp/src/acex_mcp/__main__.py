"""Allow running acex_mcp as a module: python -m acex_mcp"""
from acex_mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
