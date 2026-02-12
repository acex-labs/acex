"""Formatters for displaying configuration diffs in CLI."""

from rich.tree import Tree
from rich.text import Text
from rich.table import Table
from rich.console import Console

console = Console()


def print_diff_summary(diff):
    """Print a summary of the diff statistics."""
    from acex_devkit.configdiffer.configdiffer import Diff
    
    if not isinstance(diff, Diff):
        console.print("[red]Invalid diff object[/red]")
        return
    
    if diff.is_empty():
        console.print("[green]✓ No changes detected[/green]")
        return
    
    summary = diff.summary()
    
    table = Table(title="Configuration Diff Summary")
    table.add_column("Operation", style="bold")
    table.add_column("Count", style="cyan", justify="right")
    
    if summary.get("add", 0) > 0:
        table.add_row("Added", f"[green]{summary['add']}[/green]")
    if summary.get("remove", 0) > 0:
        table.add_row("Removed", f"[red]{summary['remove']}[/red]")
    if summary.get("change", 0) > 0:
        table.add_row("Changed", f"[yellow]{summary['change']}[/yellow]")
    
    console.print(table)


def print_diff_tree(diff, max_depth: int = None, show_values: bool = True):
    """
    Print diff as a hierarchical tree view.
    
    Args:
        diff: Diff object from configdiffer
        max_depth: Maximum depth to show (None for unlimited)
        show_values: Whether to show before/after values
    """
    from acex_devkit.configdiffer.configdiffer import Diff, DiffNode, DiffOp
    
    if not isinstance(diff, Diff):
        console.print("[red]Invalid diff object[/red]")
        return
    
    if diff.is_empty():
        console.print("[green]✓ No changes detected[/green]")
        return
    
    # Create colored title with summary
    summary = diff.summary()
    title = Text("🔀 Configuration Changes ", style="bold")
    title.append("(", style="dim")
    
    parts = []
    if summary.get("add", 0) > 0:
        parts.append((f"+{summary['add']}", "green"))
    if summary.get("remove", 0) > 0:
        parts.append((f"-{summary['remove']}", "red"))
    if summary.get("change", 0) > 0:
        parts.append((f"~{summary['change']}", "yellow"))
    
    for i, (text, color) in enumerate(parts):
        if i > 0:
            title.append(" ", style="dim")
        title.append(text, style=f"bold {color}")
    
    title.append(")", style="dim")
    
    tree = Tree(title)
    
    def add_node(parent_tree, node: DiffNode, key: str, depth: int = 0):
        """Recursively add nodes to the tree."""
        if max_depth is not None and depth > max_depth:
            return
        
        # Format the node based on operation
        if node.op == DiffOp.ADD:
            style = "green"
            prefix = "+ "
            value_str = f" = {_format_value(node.after)}" if show_values and node.after is not None else ""
        elif node.op == DiffOp.REMOVE:
            style = "red"
            prefix = "- "
            value_str = f" = {_format_value(node.before)}" if show_values and node.before is not None else ""
        elif node.op == DiffOp.CHANGE:
            style = "yellow"
            prefix = "~ "
            if show_values and node.children is None:
                # Leaf node with changed value
                value_str = f" {_format_value(node.before)} → {_format_value(node.after)}"
            else:
                value_str = ""
        else:
            style = "white"
            prefix = "  "
            value_str = ""
        
        # Create the tree node
        label = Text()
        label.append(prefix, style=f"bold {style}")
        label.append(key, style=style)
        label.append(value_str, style=style)
        
        branch = parent_tree.add(label)
        
        # Add children if they exist
        if node.children:
            for child_key, child_node in sorted(node.children.items()):
                add_node(branch, child_node, child_key, depth + 1)
    
    # Start with root's children
    if diff.root.children:
        for key, node in sorted(diff.root.children.items()):
            add_node(tree, node, key, depth=0)
    
    console.print(tree)


def print_diff_compact(diff, show_unchanged: bool = False):
    """
    Print diff in a compact, git-like format.
    
    Args:
        diff: Diff object from configdiffer
        show_unchanged: Whether to show unchanged paths
    """
    from acex_devkit.configdiffer.configdiffer import Diff, DiffNode, DiffOp
    
    if not isinstance(diff, Diff):
        console.print("[red]Invalid diff object[/red]")
        return
    
    if diff.is_empty():
        console.print("[green]✓ No changes detected[/green]")
        return
    
    changes = []
    
    def collect_changes(node: DiffNode, path: str = ""):
        """Recursively collect all changes with their paths."""
        if node.children:
            for key, child in sorted(node.children.items()):
                new_path = f"{path}.{key}" if path else key
                collect_changes(child, new_path)
        else:
            # Leaf node
            changes.append((path, node))
    
    collect_changes(diff.root)
    
    # Group by operation type
    adds = [(p, n) for p, n in changes if n.op == DiffOp.ADD]
    removes = [(p, n) for p, n in changes if n.op == DiffOp.REMOVE]
    modifications = [(p, n) for p, n in changes if n.op == DiffOp.CHANGE]
    
    if adds:
        console.print("\n[bold green]✚ Added:[/bold green]")
        for path, node in adds:
            value_str = _format_value(node.after, max_length=60)
            console.print(f"  [green]+ {path}[/green] = {value_str}")
    
    if removes:
        console.print("\n[bold red]✖ Removed:[/bold red]")
        for path, node in removes:
            value_str = _format_value(node.before, max_length=60)
            console.print(f"  [red]- {path}[/red] = {value_str}")
    
    if modifications:
        console.print("\n[bold yellow]⚡ Modified:[/bold yellow]")
        for path, node in modifications:
            before_str = _format_value(node.before, max_length=40)
            after_str = _format_value(node.after, max_length=40)
            console.print(f"  [yellow]~ {path}[/yellow]")
            console.print(f"    [red]- {before_str}[/red]")
            console.print(f"    [green]+ {after_str}[/green]")


def print_diff_flat(diff):
    """
    Print diff in a flat list format, good for quick scanning.
    
    Args:
        diff: Diff object from configdiffer
    """
    from acex_devkit.configdiffer.configdiffer import Diff, DiffNode, DiffOp
    
    if not isinstance(diff, Diff):
        console.print("[red]Invalid diff object[/red]")
        return
    
    if diff.is_empty():
        console.print("[green]✓ No changes detected[/green]")
        return
    
    changes = []
    
    def collect_changes(node: DiffNode, path: str = ""):
        """Recursively collect all changes with their paths."""
        if node.children:
            for key, child in sorted(node.children.items()):
                new_path = f"{path}.{key}" if path else key
                collect_changes(child, new_path)
        else:
            # Leaf node
            changes.append((path, node))
    
    collect_changes(diff.root)
    
    # Create table
    table = Table(title="Configuration Changes", show_lines=True)
    table.add_column("Op", style="bold", width=3)
    table.add_column("Path", style="cyan")
    table.add_column("Before", style="red", max_width=40)
    table.add_column("After", style="green", max_width=40)
    
    for path, node in changes:
        if node.op == DiffOp.ADD:
            op_symbol = "[green]+[/green]"
            before = ""
            after = _format_value(node.after, max_length=40)
        elif node.op == DiffOp.REMOVE:
            op_symbol = "[red]-[/red]"
            before = _format_value(node.before, max_length=40)
            after = ""
        else:  # CHANGE
            op_symbol = "[yellow]~[/yellow]"
            before = _format_value(node.before, max_length=40)
            after = _format_value(node.after, max_length=40)
        
        table.add_row(op_symbol, path, before, after)
    
    console.print(table)


def _format_value(value, max_length: int = 100) -> str:
    """Format a value for display, truncating if necessary."""
    import json
    
    if value is None:
        return "[dim]null[/dim]"
    
    if isinstance(value, (dict, list)):
        # For complex objects, show compact JSON
        value_str = json.dumps(value, separators=(',', ':'))
    else:
        value_str = str(value)
    
    # Truncate if too long
    if len(value_str) > max_length:
        return value_str[:max_length-3] + "..."
    
    return value_str
