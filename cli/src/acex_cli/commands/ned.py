from typing import Optional

import typer

from acex_cli.sdk import get_sdk
from acex_cli.output import display_list, display_object
from acex_client.models.generated_models import Ned

app = typer.Typer(help="NED (Network Element Driver) commands")


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    # Output (NEDs endpoint has no server-side filters or pagination)
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated columns"),
    no_header: bool = typer.Option(False, "--no-header", help="Hide table header"),
):
    """List available NEDs."""
    sdk = get_sdk(ctx.obj.get_active_context())
    result = sdk.neds.query()
    display_list(
        result,
        format=format,
        columns=columns.split(",") if columns else None,
        no_header=no_header,
        model=Ned,
        title="NEDs",
    )


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    ned_id: str,
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated fields"),
):
    """Show details for a NED."""
    sdk = get_sdk(ctx.obj.get_active_context())
    ned = sdk.neds.get(ned_id)
    display_object(
        ned,
        format=format,
        columns=columns.split(",") if columns else None,
        model=Ned,
        title=f"NED {ned_id}",
    )
