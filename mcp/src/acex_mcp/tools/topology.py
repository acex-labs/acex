"""What is physically attached to a node."""

from typing import Any

from fastmcp import FastMCP

from ..backend import call, client

READ_ONLY: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}


def _neighbor(entry: Any, *, direction: str) -> dict:
    return {
        "direction": direction,
        "local_interface": entry.local_interface,
        "remote_device": entry.remote_device,
        "remote_interface": entry.remote_interface,
        "remote_node_id": entry.remote_node_id,
        "protocol": entry.discovery_protocol,
        "collected_at": entry.collected_at,
    }


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    async def get_neighbors(node_id: int) -> dict:
        """List the devices physically cabled to a node, as discovered by LLDP/CDP.

        Args:
            node_id: From find_nodes().

        Returns `neighbors`, each with the local port it is seen on, the
        neighbour's advertised name and port, and `remote_node_id` — the
        neighbour's own node_id when ACE-X tracks it, which you can pass
        straight to get_observed_config() or get_config_drift() to inspect what
        is actually configured on the other end. It is null for devices ACE-X
        does not know.

        `direction` is "downstream" for neighbours this node sees, and
        "upstream" for nodes that report seeing this one — the two can differ
        when only one side has been collected.

        Use this before asserting anything about what is attached to a port.
        If an answer would otherwise contain "if the downstream device still
        needs this VLAN", look the neighbour up here and check its config
        instead of leaving it as a guess.
        """
        lldp = client().operations.lldp
        seen = await call(lldp.get, node_instance_id=node_id, doing=f"listing LLDP neighbours of node {node_id}")
        reverse = await call(lldp.reverse, node_instance_id=node_id, doing=f"listing nodes that see node {node_id}")
        neighbors = [_neighbor(entry, direction="downstream") for entry in seen or []]
        neighbors += [_neighbor(entry, direction="upstream") for entry in reverse or []]
        return {
            "node_id": node_id,
            "neighbors": neighbors,
            "returned": len(neighbors),
            "note": None if neighbors else "No LLDP neighbours have been collected for this node.",
        }
