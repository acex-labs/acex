"""Formatters for displaying configuration diffs in CLI."""
import json
from rich.tree import Tree
from rich.text import Text
from rich.table import Table
from rich.console import Console

console = Console()

from pydantic import BaseModel
from acex_devkit.configdiffer import Diff, ComponentDiffOp


def _as_dict(obj) -> dict:
    """Convert a Pydantic model or dict to a plain dict for iteration."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {}


def print_diff_summary(diff):
    """Print a summary of the diff statistics."""
    
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
    
    if summary.get("added", 0) > 0:
        table.add_row("Added", f"[green]{summary['added']}[/green]")
    if summary.get("removed", 0) > 0:
        table.add_row("Removed", f"[red]{summary['removed']}[/red]")
    if summary.get("changed", 0) > 0:
        table.add_row("Changed", f"[yellow]{summary['changed']}[/yellow]")
    
    console.print(table)


def print_diff_tree(diff, max_depth: int = None, show_values: bool = True):
    """
    Print diff as a hierarchical tree view.
    
    Args:
        diff: Diff object from configdiffer
        max_depth: Maximum depth to show (None for unlimited)
        show_values: Whether to show before/after values
    """
    
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
    if summary.get("added", 0) > 0:
        parts.append((f"+{summary['added']}", "green"))
    if summary.get("removed", 0) > 0:
        parts.append((f"-{summary['removed']}", "red"))
    if summary.get("changed", 0) > 0:
        parts.append((f"~{summary['changed']}", "yellow"))
    
    for i, (text, color) in enumerate(parts):
        if i > 0:
            title.append(" ", style="dim")
        title.append(text, style=f"bold {color}")
    
    title.append(")", style="dim")
    
    tree = Tree(title)
    
    # Build a hierarchical tree structure based on component paths
    # We'll use a dict to track nodes: path_tuple -> tree_node
    path_nodes = {}
    
    # Group changes by top-level section first to get counts
    sections = {}
    for change in diff.get_all_changes():
        section = change.path[0] if change.path else "root"
        if section not in sections:
            sections[section] = []
        sections[section].append(change)
    
    # Process each change and build nested structure
    for section_name in sorted(sections.keys()):
        section_changes = sections[section_name]
        
        # Create section node
        section_label = Text()
        section_label.append(section_name, style="bold cyan")
        section_label.append(f" ({len(section_changes)} changes)", style="dim")
        section_node = tree.add(section_label)
        path_nodes[(section_name,)] = section_node
        
        # Add each change, building nested path structure
        for change in section_changes:
            # Build path incrementally
            path = tuple(change.path)
            
            # Find or create parent nodes for nested path
            parent_node = section_node
            for i in range(1, len(path)):
                partial_path = path[:i+1]
                
                # Check if this is the final component or an intermediate path
                if i == len(path) - 1:
                    # This is the actual component with the change
                    if change.op == ComponentDiffOp.ADD:
                        style = "green"
                        prefix = "+ "
                    elif change.op == ComponentDiffOp.REMOVE:
                        style = "red"
                        prefix = "- "
                    else:  # CHANGE
                        style = "yellow"
                        prefix = "~ "
                    
                    # Component label
                    comp_label = Text()
                    comp_label.append(prefix, style=f"bold {style}")
                    comp_label.append(f"{change.component_type}: ", style=f"dim {style}")
                    comp_label.append(change.component_name, style=style)
                    
                    comp_node = parent_node.add(comp_label)
                    
                    if show_values:
                        # Show attributes for ADD operations
                        if change.op == ComponentDiffOp.ADD and change.after_dict:
                            for attr_name, attr_value in change.after_dict.items():
                                # Skip metadata and type fields
                                if attr_name in ['metadata', 'type']:
                                    continue
                                attr_label = Text()
                                attr_label.append("  ", style="dim")
                                attr_label.append(attr_name, style="cyan")
                                attr_label.append(": ", style="dim")
                                formatted_val = _format_value(attr_value)
                                attr_label.append(formatted_val, style="dim green" if formatted_val == "null" else "green")
                                comp_node.add(attr_label)
                        
                        # Show attributes for REMOVE operations
                        elif change.op == ComponentDiffOp.REMOVE and change.before_dict:
                            for attr_name, attr_value in change.before_dict.items():
                                # Skip metadata and type fields
                                if attr_name in ['metadata', 'type']:
                                    continue
                                attr_label = Text()
                                attr_label.append("  ", style="dim")
                                attr_label.append(attr_name, style="cyan")
                                attr_label.append(": ", style="dim")
                                formatted_val = _format_value(attr_value)
                                attr_label.append(formatted_val, style="dim red" if formatted_val == "null" else "red")
                                comp_node.add(attr_label)
                        
                        # Show changed attributes for CHANGE operations
                        elif change.op == ComponentDiffOp.CHANGE and change.changed_attributes:
                            for attr in change.changed_attributes:
                                attr_label = Text()
                                attr_label.append("  ", style="dim")
                                attr_label.append(attr.attribute_name, style="cyan")
                                attr_label.append(": ", style="dim")
                                before_val = _format_value(attr.before)
                                attr_label.append(before_val, style="dim red" if before_val == "null" else "red")
                                attr_label.append(" → ", style="dim")
                                after_val = _format_value(attr.after)
                                attr_label.append(after_val, style="dim green" if after_val == "null" else "green")
                                comp_node.add(attr_label)
                else:
                    # Intermediate path element - create if doesn't exist
                    if partial_path not in path_nodes:
                        path_label = Text()
                        path_label.append(path[i], style="dim cyan")
                        path_node = parent_node.add(path_label)
                        path_nodes[partial_path] = path_node
                    parent_node = path_nodes[partial_path]
    
    console.print(tree)


def print_diff_compact(diff, show_unchanged: bool = False):
    """
    Print diff in a compact, git-like format.
    
    Args:
        diff: Diff object from configdiffer
        show_unchanged: Whether to show unchanged paths
    """
    
    if not isinstance(diff, Diff):
        console.print("[red]Invalid diff object[/red]")
        return
    
    if diff.is_empty():
        console.print("[green]✓ No changes detected[/green]")
        return
    
    if diff.added:
        console.print("\n[bold green]✚ Added:[/bold green]")
        for change in diff.added:
            path = change.get_path_str()
            console.print(f"  [green]+ {change.component_type_name_name}:[/green] {change.component_name}")
    
    if diff.removed:
        console.print("\n[bold red]✖ Removed:[/bold red]")
        for change in diff.removed:
            path = change.get_path_str()
            console.print(f"  [red]- {change.component_type_name_name}:[/red] {change.component_name}")
    
    if diff.changed:
        console.print("\n[bold yellow]⚡ Modified:[/bold yellow]")
        for change in diff.changed:
            console.print(f"  [yellow]~ {change.component_type_name_name}:[/yellow] {change.component_name}")
            if change.changed_attributes:
                for attr in change.changed_attributes:
                    before_str = _format_value(attr.before, max_length=40)
                    after_str = _format_value(attr.after, max_length=40)
                    console.print(f"    {attr.attribute_name}:")
                    console.print(f"      [red]- {before_str}[/red]")
                    console.print(f"      [green]+ {after_str}[/green]")


def print_diff_flat(diff):
    """
    Print diff in a flat list format, good for quick scanning.
    
    Args:
        diff: Diff object from configdiffer
    """
    
    if not isinstance(diff, Diff):
        console.print("[red]Invalid diff object[/red]")
        return
    
    if diff.is_empty():
        console.print("[green]✓ No changes detected[/green]")
        return
    
    # Create table
    table = Table(title="Configuration Changes", show_lines=True)
    table.add_column("Op", style="bold", width=3)
    table.add_column("Type", style="cyan")
    table.add_column("Component", style="bold")
    table.add_column("Attribute", style="magenta")
    table.add_column("Before", style="red", max_width=30)
    table.add_column("After", style="green", max_width=30)
    
    for change in diff.added:
        table.add_row(
            "[green]+[/green]",
            change.component_type_name_name,
            change.component_name,
            "[dim]--[/dim]",
            "",
            "[dim]new component[/dim]"
        )
    
    for change in diff.removed:
        table.add_row(
            "[red]-[/red]",
            change.component_type_name_name,
            change.component_name,
            "[dim]--[/dim]",
            "[dim]component deleted[/dim]",
            ""
        )
    
    for change in diff.changed:
        if change.changed_attributes:
            for i, attr in enumerate(change.changed_attributes):
                table.add_row(
                    "[yellow]~[/yellow]" if i == 0 else "",
                    change.component_type_name_name if i == 0 else "",
                    change.component_name if i == 0 else "",
                    attr.attribute_name,
                    _format_value(attr.before, max_length=30),
                    _format_value(attr.after, max_length=30)
                )
        else:
            table.add_row(
                "[yellow]~[/yellow]",
                change.component_type_name_name,
                change.component_name,
                "[dim]--[/dim]",
                "[dim]changed[/dim]",
                "[dim]changed[/dim]"
            )
    
    console.print(table)


def _format_value(value, max_length: int = 100) -> str:
    """Format a value for display, truncating if necessary."""
    
    if value is None:
        return "null"
    
    # Check if this is an AttributeValue (Pydantic model or dict with 'value' key)
    if isinstance(value, BaseModel) and hasattr(value, 'value'):
        value = value.value
        if value is None:
            return "null"
    elif isinstance(value, dict) and 'value' in value:
        value = value['value']
        if value is None:
            return "null"
    
    if isinstance(value, (dict, list)):
        # For complex objects, show compact JSON
        value_str = json.dumps(value, separators=(',', ':'))
    else:
        value_str = str(value)
    
    # Truncate if too long
    if len(value_str) > max_length:
        return value_str[:max_length-3] + "..."
    
    return value_str
