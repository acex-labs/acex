"""Main CLI application entry point."""

import typer
import importlib
import pkgutil
import pathlib
from acex_cli.context import CLIContext

app = typer.Typer(
    name="acex",
    help="ACE-X - Automation & Control Ecosystem CLI",
    add_completion=True,
)

# Dynamiskt importera och lägg till alla Typer-appar från commands-mappen
commands_path = pathlib.Path(__file__).parent / "commands"
for module_info in pkgutil.iter_modules([str(commands_path)]):
    if module_info.name.startswith("_"):
        continue
    module = importlib.import_module(f"acex_cli.commands.{module_info.name}")
    if hasattr(module, "app"):
        app.add_typer(module.app, name=module_info.name)

cli_context = CLIContext()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    ctx.obj = cli_context
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def version():
    """Show version information."""
    from acex_cli import __version__
    console.print(f"ACE-X CLI version: {__version__}")


if __name__ == "__main__":
    app()

