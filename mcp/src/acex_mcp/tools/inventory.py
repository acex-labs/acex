"""Finding things: nodes, the hardware under them, and where they live."""

from typing import Any

from fastmcp import FastMCP

from ..backend import call, client

READ_ONLY: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}


def _node_row(item: Any) -> dict:
    """One row of a node list — enough to pick a node, nothing more."""
    return {
        "node_id": item.id,
        "hostname": item.hostname,
        "site": item.site,
        "role": item.role,
        "regions": item.regions,
        "vendor": item.vendor,
        "os": item.os,
        "status": str(item.status) if item.status else None,
    }


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    async def find_nodes(
        hostname: str | None = None,
        site: str | None = None,
        region: str | None = None,
        role: str | None = None,
        vendor: str | None = None,
        os: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Find network nodes, optionally filtered. Start here.

        A node is a deployed device: a desired configuration bound to a piece of
        hardware. This is the thing operators mean when they say "switch",
        "router" or "device", and the `node_id` it returns is what every other
        tool takes.

        Args:
            hostname: Exact hostname, e.g. "SW-CORE-01".
            site: Site name, e.g. "cph01".
            region: Region name.
            role: Function, e.g. "core", "access".
            vendor: Hardware vendor, e.g. "cisco".
            os: Device OS, e.g. "ios".
            status: One of "planned", "init", "active", "decommissioned".
            limit: Maximum rows to return.

        Returns `{"nodes": [...], "total": n, "returned": m}`. Each row carries
        node_id, hostname, site, role, regions, vendor, os and status. It does
        NOT carry configuration — use get_desired_config, get_observed_config or
        get_config_drift once you have a node_id.

        If `total` exceeds `returned`, narrow the filters rather than raising
        the limit.
        """
        result = await call(
            client().inventory.node_instances.query,
            limit=limit,
            hostname=hostname,
            site=site,
            region=region,
            role=role,
            vendor=vendor,
            os=os,
            status=status,
            doing="searching for nodes",
        )
        return {
            "nodes": [_node_row(item) for item in result.items],
            "total": result.total,
            "returned": len(result.items),
        }

    @mcp.tool(annotations=READ_ONLY)
    async def get_node(node_id: int) -> dict:
        """Get one node with its hardware and its identity.

        Args:
            node_id: From find_nodes().

        Returns the node's identity (hostname, site, role, regions, status), the
        physical hardware it runs on (vendor, model, serial number, OS version,
        driver), and the internal ids that link them — `logical_node_id` for the
        desired configuration and `asset_ref_id` for the hardware record. Those
        ids are for traceability; no tool requires them, they all take node_id.

        This returns no configuration. For that use get_desired_config (what it
        should be), get_observed_config (what was last collected from it) or
        get_config_drift (the difference).
        """
        node = await call(client().inventory.node_instances.get, node_id, doing=f"looking up node {node_id}")
        asset = node.asset
        logical = node.logical_node
        hardware: dict[str, Any] = {"kind": getattr(asset, "type", None), "ned_id": getattr(asset, "ned_id", None)}
        if getattr(asset, "type", None) == "asset_cluster":
            # A cluster stands in for several chassis acting as one node.
            hardware["cluster_name"] = getattr(asset, "name", None)
            hardware["members"] = [
                {
                    "vendor": member.vendor,
                    "hardware_model": member.hardware_model,
                    "serial_number": member.serial_number,
                    "os": member.os,
                    "os_version": member.os_version,
                }
                for member in getattr(asset, "assets", [])
            ]
        else:
            hardware.update(
                {
                    "vendor": getattr(asset, "vendor", None),
                    "hardware_model": getattr(asset, "hardware_model", None),
                    "serial_number": getattr(asset, "serial_number", None),
                    "os": getattr(asset, "os", None),
                    "os_version": getattr(asset, "os_version", None),
                }
            )

        return {
            "node_id": node.id,
            "hostname": logical.hostname,
            "site": logical.site,
            "role": logical.role,
            "sequence": logical.sequence,
            "regions": node.regions,
            "status": str(node.status) if node.status else None,
            "hardware": hardware,
            "logical_node_id": node.logical_node_id,
            "asset_ref_id": node.asset_ref_id,
            "created_at": node.created_at,
            "updated_at": node.updated_at,
        }

    @mcp.tool(annotations=READ_ONLY)
    async def find_assets(
        vendor: str | None = None,
        os: str | None = None,
        hardware_model: str | None = None,
        serial_number: str | None = None,
        assigned: bool | None = None,
        limit: int = 50,
    ) -> dict:
        """Find physical hardware in inventory, whether or not it is deployed.

        Assets are chassis records — they exist independently of any
        configuration. Use this for hardware questions ("what spare kit do we
        have", "which serial number is that", "what are we running on Nexus").
        For questions about configured devices use find_nodes() instead.

        Args:
            vendor: e.g. "cisco".
            os: e.g. "ios".
            hardware_model: e.g. "C9300-48P".
            serial_number: Exact serial number.
            assigned: True for hardware already bound to a node, False for spare.
            limit: Maximum rows to return.
        """
        result = await call(
            client().inventory.assets.query,
            limit=limit,
            vendor=vendor,
            os=os,
            hardware_model=hardware_model,
            serial_number=serial_number,
            assigned=assigned,
            doing="searching for assets",
        )
        return {
            "assets": [
                {
                    "asset_id": item.id,
                    "vendor": item.vendor,
                    "hardware_model": item.hardware_model,
                    "serial_number": item.serial_number,
                    "os": item.os,
                    "os_version": item.os_version,
                    "ned_id": item.ned_id,
                }
                for item in result.items
            ],
            "total": result.total,
            "returned": len(result.items),
        }

    @mcp.tool(annotations=READ_ONLY)
    async def list_sites(
        name: str | None = None,
        city: str | None = None,
        country: str | None = None,
        region: str | None = None,
        limit: int = 100,
    ) -> dict:
        """List physical sites — the locations nodes live at.

        Use this to answer "which sites exist" or to find a site's exact name
        before passing it to find_nodes(site=...).

        Args:
            name: Exact site name.
            city: Filter by city.
            country: Filter by country.
            region: Only sites in this region.
            limit: Maximum rows to return.
        """
        result = await call(
            client().inventory.sites.query,
            limit=limit,
            name=name,
            city=city,
            country=country,
            region=region,
            doing="listing sites",
        )
        return {
            "sites": [
                {
                    "name": item.name,
                    "display_name": item.display_name,
                    "city": item.city,
                    "country": item.country,
                    "description": item.description,
                }
                for item in result.items
            ],
            "total": result.total,
            "returned": len(result.items),
        }

    @mcp.tool(annotations=READ_ONLY)
    async def list_regions(limit: int = 100) -> dict:
        """List regions — logical groupings of sites.

        Use this to find a region's exact name before passing it to
        find_nodes(region=...) or list_sites(region=...).
        """
        result = await call(client().inventory.regions.query, limit=limit, doing="listing regions")
        return {
            "regions": [
                {
                    "name": item.name,
                    "display_name": item.display_name,
                    "description": item.description,
                    "sites": [site.name for site in item.sites],
                }
                for item in result.items
            ],
            "total": result.total,
            "returned": len(result.items),
        }
