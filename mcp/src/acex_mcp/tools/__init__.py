from fastmcp import FastMCP

from . import actions, configuration, inventory, topology


def register_all(mcp: FastMCP) -> None:
    inventory.register(mcp)
    configuration.register(mcp)
    topology.register(mcp)
    actions.register(mcp)
