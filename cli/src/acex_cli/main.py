"""Main CLI application entry point."""

import typer
from rich.console import Console

app = typer.Typer(
    name="acex",
    help="ACE-X - Automation & Control Ecosystem CLI",
    add_completion=False,
)
console = Console()


@app.command()
def version():
    """Show version information."""
    from acex_cli import __version__
    console.print(f"ACE-X CLI version: {__version__}")


@app.command()
def run(file: str):
    """Run an automation file."""
    console.print(f"[green]Running automation: {file}[/green]")
    # TODO: Implement automation execution


@app.command()
def list():
    """List available automations."""
    console.print("[blue]Available automations:[/blue]")
    # TODO: Implement automation listing


@app.command()
def status():
    """Check system status."""
    console.print("[yellow]System Status:[/yellow]")
    # TODO: Implement status check


if __name__ == "__main__":
    app()
