from fastmcp import FastMCP

from . import configuration, inventory, topology


def register_all(mcp: FastMCP) -> None:
    inventory.register(mcp)
    configuration.register(mcp)
    topology.register(mcp)
