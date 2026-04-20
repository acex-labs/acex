"""Unified output formatting for CLI commands.

Supports table, json, and csv output with column selection,
header control, and pagination display.
"""

import csv
import io
import json
from typing import Optional

from rich.table import Table
from rich.console import Console

console = Console()


def display_list(
    result,
    *,
    format: str = "table",
    columns: Optional[list[str]] = None,
    no_header: bool = False,
    model=None,
    title: str = "",
):
    """Display a paginated list of items."""
    items = result.items if hasattr(result, "items") else result
    total = result.total if hasattr(result, "total") else len(items)

    if not items:
        console.print(f"No {title.lower() or 'items'} found.")
        return

    # Resolve columns
    if columns is None:
        if model is not None:
            columns = list(model.model_fields.keys())
        elif hasattr(items[0], "model_fields"):
            columns = list(items[0].model_fields.keys())

    rows = _to_dicts(items)

    if format == "json":
        _print_json_list(rows, result)
    elif format == "csv":
        _print_csv(rows, columns, no_header)
    else:
        _print_table(
            rows, columns, no_header, title,
            total=total,
            limit=getattr(result, "limit", None),
            offset=getattr(result, "offset", None),
        )


def display_object(
    obj,
    *,
    format: str = "table",
    columns: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    model=None,
    title: str = "",
):
    """Display a single object."""
    if obj is None:
        console.print("Not found.")
        return

    data = _to_dict(obj)

    # Filter fields
    if columns:
        data = {k: v for k, v in data.items() if k in columns}
    elif model:
        fields = list(model.model_fields.keys())
        data = {k: v for k, v in data.items() if k in fields}

    if exclude:
        data = _deep_exclude(data, exclude)

    if format == "json":
        console.print_json(json.dumps(data, default=str))
    elif format == "csv":
        cols = list(data.keys())
        _print_csv([data], cols, no_header=False)
    else:
        _print_object_table(data, title)


# ── Internal helpers ────────────────────────────────────────────


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


def _to_dicts(items):
    return [_to_dict(item) for item in items]


def _print_json_list(rows, result):
    output = {"items": rows, "total": getattr(result, "total", len(rows))}
    if hasattr(result, "limit"):
        output["limit"] = result.limit
        output["offset"] = result.offset
    console.print_json(json.dumps(output, default=str))


def _print_table(rows, columns, no_header, title, total=None, limit=None, offset=None):
    caption = None
    if total is not None and limit is not None and total > len(rows):
        start = (offset or 0) + 1
        end = (offset or 0) + len(rows)
        caption = f"Showing {start}-{end} of {total}"

    table = Table(
        title=title if not no_header else None,
        caption=caption,
        show_header=not no_header,
    )
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*(_format_cell(row.get(col, "")) for col in columns))
    console.print(table)


def _print_csv(rows, columns, no_header):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    if not no_header:
        writer.writeheader()
    for row in rows:
        writer.writerow({k: _format_cell(row.get(k, "")) for k in columns})
    console.print(output.getvalue().rstrip(), highlight=False)


def _print_object_table(data, title):
    # Separate scalar fields from nested objects
    scalars = {}
    nested = {}
    for field, value in data.items():
        if isinstance(value, dict) and value:
            nested[field] = value
        else:
            scalars[field] = value

    # Main table with scalar fields
    table = Table(title=title, show_header=False, title_style="bold")
    table.add_column("Field", style="bold cyan", min_width=18)
    table.add_column("Value", style="white")
    for field, value in scalars.items():
        table.add_row(field, _format_cell(value))
    console.print(table)

    # Nested objects as separate sections
    for section_name, section_data in nested.items():
        section_table = Table(
            title=f"  {section_name}",
            show_header=False,
            title_style="bold cyan",
            title_justify="left",
            padding=(0, 1),
        )
        section_table.add_column("Field", style="dim cyan", min_width=18)
        section_table.add_column("Value", style="white")
        _add_nested_rows(section_table, section_data)
        console.print(section_table)


def _deep_exclude(data, paths):
    """Remove keys from data, supporting dotted paths like 'logical_node.configuration'."""
    top_level = {p for p in paths if "." not in p}
    nested = {}
    for p in paths:
        if "." in p:
            parent, child = p.split(".", 1)
            nested.setdefault(parent, []).append(child)

    result = {}
    for k, v in data.items():
        if k in top_level:
            continue
        if k in nested and isinstance(v, dict):
            result[k] = _deep_exclude(v, nested[k])
        else:
            result[k] = v
    return result


def _add_nested_rows(table, data):
    """Add rows for a nested dict section."""
    for field, value in data.items():
        if isinstance(value, dict) and value:
            # Flatten one level of simple dicts inline
            if not any(isinstance(v, (dict, list)) for v in value.values()):
                for k, v in value.items():
                    table.add_row(f"  {field}.{k}", _format_cell(v))
            else:
                table.add_row(field, _format_cell(value))
        elif isinstance(value, list):
            if len(value) == 0:
                table.add_row(field, "-")
            elif len(value) > 3:
                table.add_row(field, f"[{len(value)} items]")
            else:
                table.add_row(field, _format_cell(value))
        else:
            table.add_row(field, _format_cell(value))


def _format_cell(value) -> str:
    if value is None:
        return ""
    from enum import Enum
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict) and not value:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value)
