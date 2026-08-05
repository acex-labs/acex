import typer
from acex_client.models.generated_models import AssetResponse

from acex_cli.output import display_list, display_object
from acex_cli.sdk import get_sdk

app = typer.Typer(help="Asset resource commands")


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    # Filters (match backend query params)
    vendor: str | None = typer.Option(None, help="Filter by vendor (prefix match)"),
    os: str | None = typer.Option(None, "--os", help="Filter by OS"),
    hardware_model: str | None = typer.Option(None, help="Filter by hardware model"),
    ned_id: str | None = typer.Option(None, help="Filter by NED ID"),
    serial_number: str | None = typer.Option(None, help="Filter by serial number"),
    assigned: bool | None = typer.Option(None, help="Filter assigned/unassigned"),
    # Pagination
    limit: int = typer.Option(100, "--limit", "-l", help="Max items to return"),
    offset: int = typer.Option(0, "--offset", help="Items to skip"),
    # Output
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: str | None = typer.Option(None, "--columns", "-c", help="Comma-separated columns"),
    no_header: bool = typer.Option(False, "--no-header", help="Hide table header"),
):
    """List assets with optional filters."""
    sdk = get_sdk(ctx.obj.get_active_context())
    filters = _compact(
        vendor=vendor,
        os=os,
        hardware_model=hardware_model,
        ned_id=ned_id,
        serial_number=serial_number,
        assigned=assigned,
    )
    result = sdk.assets.query(limit=limit, offset=offset, **filters)
    display_list(
        result,
        format=format,
        columns=columns.split(",") if columns else None,
        no_header=no_header,
        model=AssetResponse,
        title="Assets",
    )


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    asset_id: str,
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: str | None = typer.Option(None, "--columns", "-c", help="Comma-separated fields"),
):
    """Show details for an asset."""
    sdk = get_sdk(ctx.obj.get_active_context())
    asset = sdk.assets.get(asset_id)
    display_object(
        asset,
        format=format,
        columns=columns.split(",") if columns else None,
        model=AssetResponse,
        title=f"Asset {asset_id}",
    )


def _compact(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}
