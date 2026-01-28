import typer
from acex_cli.context import CLIContext

app = typer.Typer(help="Context management. Configure API url etc.")

@app.command("verify-ssl")
def verify_ssl(
    value: str = typer.Argument(..., help="Set verify_ssl to true or false", show_default=False, case_sensitive=False),
    ctx: typer.Context = typer.Context
):
    """Update verify_ssl for the active context. Usage: acex context verify-ssl true|false"""
    value = value.lower()
    if value not in ("true", "false"):
        typer.echo("Value must be 'true' or 'false'.")
        raise typer.Exit(1)
    bool_value = value == "true"
    active = ctx.obj.data.get("active_context")
    contexts = ctx.obj.data.get("contexts", {})
    if not active or active not in contexts:
        typer.echo("No active context selected.")
        raise typer.Exit(1)
    contexts[active]["verify_ssl"] = bool_value
    ctx.obj.save()
    typer.echo(f"verify_ssl for active context '{active}' set to {bool_value}.")

@app.command()
def add(
    name: str = typer.Option(..., "--name", help="Context name"),
    url: str = typer.Option(..., "--url", help="API URL"),
    verify_ssl: bool = typer.Option(True, "--verify-ssl/--no-verify-ssl", help="Verify SSL certificates"),
    ctx: typer.Context = typer.Context
):
    """Set or update a context."""
    ctx.obj.set_context(name, url, verify_ssl=verify_ssl)
    typer.echo(f"Context '{name}' set to {url} (verify_ssl={verify_ssl}) and activated.")

@app.command()
def list(ctx: typer.Context):
    """List all saved contexts."""
    contexts = ctx.obj.data.get("contexts", {})
    active = ctx.obj.data.get("active_context")
    if not contexts:
        typer.echo("No contexts saved.")
        return
    for name, data in contexts.items():
        marker = "*" if name == active else " "
        url = data.get("url", "")
        typer.echo(f"{marker} {name}: {url}")

@app.command()
def use(name: str, ctx: typer.Context):
    """Set active context by name."""
    ctx.obj.set_active(name)
    typer.echo(f"Active context set to '{name}'")

@app.command()
def show(ctx: typer.Context):
    """Show active context details."""
    context = ctx.obj.get_active_context()
    if context:
        typer.echo(f"Active context: {context}")
    else:
        typer.echo("No active context set.")

