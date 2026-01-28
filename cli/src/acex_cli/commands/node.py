import typer
from acex_cli.sdk import get_sdk
from acex_cli.print_utils import print_list_table, print_object
from acex_client.models.models import Node

app = typer.Typer(help="Node resource commands")

@app.command()
def list(ctx: typer.Context):
    """List all assets."""
    sdk = get_sdk(ctx.obj.get_active_context())
    nodes = sdk.node_instances.get_all()
    if not nodes:
        typer.echo("No nodes found.")
        return
    
    print_list_table(nodes, pydantic_class=Node, title="Node Instances")

@app.command()
def show(ctx: typer.Context, node_id: str):
    """Show details for an asset."""
    sdk = get_sdk(ctx.obj.get_active_context())
    node = sdk.node_instances.get(node_id)

    print_object(node, pydantic_class=Node, title=f"Node {node_id} details")
