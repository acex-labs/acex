from typing import Optional

import typer

from acex_cli.sdk import get_sdk
from acex_cli.output import display_list, display_object
from acex_client.models.generated_models import LogicalNode

app = typer.Typer(help="Logical node resource commands")


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    # Filters (match backend query params)
    role: Optional[str] = typer.Option(None, help="Filter by role (prefix match)"),
    site: Optional[str] = typer.Option(None, help="Filter by site (prefix match)"),
    hostname: Optional[str] = typer.Option(None, help="Filter by hostname (prefix match)"),
    sequence: Optional[int] = typer.Option(None, help="Filter by sequence number"),
    assigned: Optional[bool] = typer.Option(None, help="Filter assigned/unassigned"),
    # Pagination
    limit: int = typer.Option(100, "--limit", "-l", help="Max items to return"),
    offset: int = typer.Option(0, "--offset", help="Items to skip"),
    # Output
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated columns"),
    no_header: bool = typer.Option(False, "--no-header", help="Hide table header"),
):
    """List logical nodes with optional filters."""
    sdk = get_sdk(ctx.obj.get_active_context())
    filters = _compact(
        role=role, site=site, hostname=hostname,
        sequence=sequence, assigned=assigned,
    )
    result = sdk.logical_nodes.query(limit=limit, offset=offset, **filters)
    display_list(
        result,
        format=format,
        columns=columns.split(",") if columns else None,
        no_header=no_header,
        model=LogicalNode,
        title="Logical Nodes",
    )


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    logical_node_id: str,
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated fields"),
):
    """Show details for a logical node."""
    sdk = get_sdk(ctx.obj.get_active_context())
    logical_node = sdk.logical_nodes.get(logical_node_id)
    display_object(
        logical_node,
        format=format,
        columns=columns.split(",") if columns else None,
        title=f"Logical Node {logical_node_id}",
    )


def _compact(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}
