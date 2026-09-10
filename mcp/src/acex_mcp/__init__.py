"""ACE-X MCP Server - Model Context Protocol server for ACE-X."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("acex-mcp")
except PackageNotFoundError:  # source tree without an install
    __version__ = "0.0.0"
