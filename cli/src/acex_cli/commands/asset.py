import typer
from acex_cli.sdk import get_sdk
from acex_cli.print_utils import print_list_table, print_object
from acex_client.models.models import AssetResponse

app = typer.Typer(help="Asset resource commands")

@app.command()
def list(ctx: typer.Context):
    """List all assets."""
    sdk = get_sdk(ctx.obj.get_active_context())
    assets = sdk.assets.get_all()
    if not assets:
        typer.echo("No assets found.")
        return
    
    print_list_table(assets, pydantic_class=AssetResponse, title="Assets")

@app.command()
def show(ctx: typer.Context, asset_id: str):
    """Show details for an asset."""
    sdk = get_sdk(ctx.obj.get_active_context())
    asset = sdk.assets.get(asset_id)

    print_object(asset, pydantic_class=AssetResponse, title=f"Asset {asset_id} details")
