"""Assembly of the MCP server."""

import logging

from fastmcp import FastMCP

from . import prompts, resources, tools
from .auth import build_verifier
from .config import settings
from .middleware import CallerTokenMiddleware, ToolLoggingMiddleware

INSTRUCTIONS = """\
ACE-X is an infrastructure-as-code platform for network devices: it holds the
configuration each device is intended to have, and snapshots of what has
actually been collected from them.

Start with find_nodes() to locate a device — every other tool takes the node_id
it returns. Read the acex://glossary resource before answering configuration
questions; ACE-X distinguishes desired configuration from observed snapshots,
and the difference matters. All tools are read-only.
"""


def create_app() -> FastMCP:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mcp = FastMCP(
        "ACE-X",
        instructions=INSTRUCTIONS,
        auth=build_verifier(),
    )

    mcp.add_middleware(CallerTokenMiddleware())
    mcp.add_middleware(ToolLoggingMiddleware())

    tools.register_all(mcp)
    resources.register(mcp)
    prompts.register(mcp)

    return mcp


def run() -> None:
    """Entry point for the `acex-mcp` command."""
    mcp = create_app()
    if settings.is_stdio:
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="http", host=settings.host, port=settings.port, path=settings.path)
