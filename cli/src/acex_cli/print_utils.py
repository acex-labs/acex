"""Specialized display helpers for non-standard output (config commands, etc.)."""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def print_commands_box(commands: str, node_id: str):
    """Print CLI commands in a styled panel box."""
    syntax = Syntax(commands, "bash", theme="monokai", line_numbers=True, word_wrap=True)
    console.print(
        Panel(
            syntax,
            title=f"[bold cyan]node_id: {node_id}[/bold cyan]",
            subtitle="[dim]commands to apply[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
