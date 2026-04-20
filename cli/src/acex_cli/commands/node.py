import base64
import json
from typing import Optional

import requests
import typer

from acex_cli.sdk import get_sdk
from acex_cli.output import display_list, display_object
from acex_cli.print_utils import print_commands_box
from acex_devkit.models import NodeListItem
from acex_devkit.models.composed_configuration import ComposedConfiguration
from acex_cli.diff_formatters import (
    print_diff_summary,
    print_diff_tree,
    print_diff_compact,
    print_diff_flat,
)


# ── Temporary REST helpers (replace with SDK methods) ───────────

def _request_get(sdk, path: str, params: Optional[dict] = None) -> requests.Response:
    verify = getattr(getattr(sdk, "rest", None), "verify", True)
    url = f"{sdk.api_url}{path}"
    response = requests.get(url, params=params, verify=verify)
    response.raise_for_status()
    return response


def _get_connection(sdk, node_id):
    return _request_get(sdk, f"/inventory/management_connections/?node_id={node_id}").json()


def _get_rendered_config(sdk, node_id: str) -> str:
    return _request_get(sdk, f"/inventory/node_instances/{node_id}/config").text


def _get_latest_observed_config(sdk, node_id: str, output: str) -> dict:
    return _request_get(sdk, f"/operations/device_configs/{node_id}/latest?output={output}").json()


def _decode_config_content(content: str) -> str:
    return base64.b64decode(content).decode("utf-8", errors="replace")


def _fetch_node_instance(sdk, identifier: str):
    """Resolve identifier to full NodeResponse. Used by show/apply that need asset info."""
    if identifier.isdigit():
        node = sdk.node_instances.get(identifier)
    else:
        result = sdk.node_instances.query(hostname=identifier)
        if len(result) == 0:
            typer.echo(f"Node '{identifier}' not found.")
            raise typer.Exit(1)
        if len(result) > 1:
            typer.echo(f"Multiple nodes match '{identifier}':")
            from acex_cli.output import display_list
            display_list(result, columns=["id", "hostname", "site", "status"], title="")
            raise typer.Exit(1)
        node = sdk.node_instances.get(result.items[0].id)
    if not node:
        typer.echo(f"Node '{identifier}' not found.")
        raise typer.Exit(1)
    return node


def _resolve_node_quick(sdk, identifier: str):
    """Resolve to a lightweight NodeListItem. One API call, no full get()."""
    if identifier.isdigit():
        result = sdk.node_instances.query(limit=1, offset=0, asset_ref_id=None)
        # For numeric ID, just return a minimal object
        node = sdk.node_instances.get(identifier)
        if not node:
            typer.echo(f"Node '{identifier}' not found.")
            raise typer.Exit(1)
        return node
    result = sdk.node_instances.query(hostname=identifier)
    if len(result) == 0:
        typer.echo(f"Node '{identifier}' not found.")
        raise typer.Exit(1)
    if len(result) > 1:
        typer.echo(f"Multiple nodes match '{identifier}':")
        from acex_cli.output import display_list
        display_list(result, columns=["id", "hostname", "site", "status"], title="")
        raise typer.Exit(1)
    return result.items[0]


def _compile_local(sdk, identifier: str, config_maps_dir: str):
    """Compile config locally from config maps on disk. Returns ComposedConfiguration."""
    import os
    import importlib.util
    import sys

    try:
        from acex.config_map import ConfigMap
        from acex.configuration import Configuration
        from acex.config_map.context import ConfigMapContext
    except ImportError:
        typer.echo("Backend package 'acex' not installed. Run: pip install -e ../backend")
        raise typer.Exit(1)

    if not os.path.isdir(config_maps_dir):
        typer.echo(f"Directory not found: {config_maps_dir}")
        raise typer.Exit(1)

    # Fetch logical node from API (we need its attributes for filter matching)
    quick = _resolve_node_quick(sdk, identifier)
    logical_node = sdk.logical_nodes.get(quick.logical_node_id)
    if not logical_node:
        typer.echo("Logical node not found.")
        raise typer.Exit(1)

    # Discover config maps from local directory
    config_maps = []
    for root, _, files in os.walk(config_maps_dir):
        for f in files:
            if not f.endswith(".py") or f.startswith("_"):
                continue
            file_path = os.path.join(root, f)
            module_name = f"_local_cm_{os.path.splitext(f)[0]}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                typer.echo(f"Warning: failed to load {file_path}: {e}")
                continue
            for name, obj in module.__dict__.items():
                if isinstance(obj, ConfigMap) and not isinstance(obj, type):
                    config_maps.append((name, file_path, obj))

    typer.echo(f"Discovered {len(config_maps)} config maps in {config_maps_dir}")

    # Filter and compile
    configuration = Configuration(logical_node.id)
    context = ConfigMapContext(logical_node, configuration, integrations=None)

    matched = 0
    for name, file_path, cm in config_maps:
        if cm.filters is not None:
            match = False
            for exp in cm.filters.as_alternatives():
                if exp.match(logical_node):
                    match = True
                    break
            if not match:
                continue
        matched += 1
        try:
            cm.compile(context)
        except Exception as e:
            typer.echo(f"Error in {name} ({file_path}): {e}")

    typer.echo(f"Compiled {matched} matching config maps")
    return configuration.as_model()


def _fetch_desired_config(sdk, identifier: str):
    """Resolve + fetch config. Avoids unnecessary get() when possible."""
    quick = _resolve_node_quick(sdk, identifier)
    logical_node_id = getattr(quick, "logical_node_id", None)

    logical_node = sdk.logical_nodes.get(logical_node_id)
    if not logical_node:
        typer.echo("Logical node not found.")
        raise typer.Exit(1)

    config = getattr(logical_node, "configuration", None)
    if config is None:
        typer.echo("No desired configuration found.")
        raise typer.Exit(1)

    # Return quick node + config. Config commands that need full NodeResponse
    # (e.g. render, apply) will call _fetch_node_instance separately.
    return quick, config


# ── App setup ───────────────────────────────────────────────────

app = typer.Typer(help="Node resource commands")
config_app = typer.Typer(help="Node configuration commands")
config_show_app = typer.Typer(help="Show configuration")
config_diff_app = typer.Typer(help="Configuration diff commands")

app.add_typer(config_app, name="config")
config_app.add_typer(config_show_app, name="show")
config_app.add_typer(config_diff_app, name="diff")


# ── Node list / show ────────────────────────────────────────────

@app.command("list")
def list_cmd(
    ctx: typer.Context,
    # Filters (match backend query params)
    site: Optional[str] = typer.Option(None, help="Filter by site (prefix match)"),
    hostname: Optional[str] = typer.Option(None, help="Filter by hostname (prefix match)"),
    logical_node_id: Optional[int] = typer.Option(None, help="Filter by logical node ID"),
    asset_ref_id: Optional[int] = typer.Option(None, help="Filter by asset ref ID"),
    status: Optional[str] = typer.Option(None, help="Filter by status (planned, init, active, decommissioned)"),
    # Pagination
    limit: int = typer.Option(100, "--limit", "-l", help="Max items to return"),
    offset: int = typer.Option(0, "--offset", help="Items to skip"),
    # Output
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated columns"),
    no_header: bool = typer.Option(False, "--no-header", help="Hide table header"),
):
    """List node instances with optional filters."""
    sdk = get_sdk(ctx.obj.get_active_context())
    filters = _compact(
        site=site, hostname=hostname, logical_node_id=logical_node_id,
        asset_ref_id=asset_ref_id, status=status,
    )
    result = sdk.node_instances.query(limit=limit, offset=offset, **filters)
    display_list(
        result,
        format=format,
        columns=columns.split(",") if columns else ["id", "hostname", "site", "status", "vendor", "os", "ned_id"],
        no_header=no_header,
        model=NodeListItem,
        title="Node Instances",
    )


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    node: str = typer.Argument(help="Node ID or hostname"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    columns: Optional[str] = typer.Option(None, "--columns", "-c", help="Comma-separated fields"),
):
    """Show details for a node instance (by ID or hostname)."""
    sdk = get_sdk(ctx.obj.get_active_context())
    resolved = _resolve_node(sdk, node)
    flat = _flatten_node(resolved)
    display_object(
        flat,
        format=format,
        columns=columns.split(",") if columns else None,
        title=f"Node {node}",
    )


# ── Config show commands ────────────────────────────────────────

@config_show_app.command("local")
def config_show_local(
    ctx: typer.Context,
    node: str = typer.Argument(help="Node ID or hostname"),
    dir: str = typer.Option(..., "--dir", "-d", help="Path to local config_maps directory"),
    render: bool = typer.Option(False, "--render", help="Show rendered device config"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Drill into section"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Compile config locally from config maps on disk."""
    sdk = get_sdk(ctx.obj.get_active_context())
    composed = _compile_local(sdk, node, dir)

    if render:
        node_instance = _fetch_node_instance(sdk, node)
        ned = sdk.neds.get_driver_instance(node_instance.asset.ned_id)
        _print_rendered(ned.render(composed, node_instance.asset))
    else:
        _print_parsed_config(composed.model_dump(), path=path, format=format, title=f"Local config — {node}")


@config_show_app.command("desired")
def config_show_desired(
    ctx: typer.Context,
    node: str = typer.Argument(help="Node ID or hostname"),
    render: bool = typer.Option(False, "--render", help="Show rendered device config"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Drill into section, e.g. system.ntp, interfaces"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Show desired config."""
    import time
    t0 = time.time()
    sdk = get_sdk(ctx.obj.get_active_context())
    t1 = time.time()

    if render:
        node_instance = _fetch_node_instance(sdk, node)
        logical_node = sdk.logical_nodes.get(node_instance.logical_node_id)
        config = getattr(logical_node, "configuration", None)
        ned = sdk.neds.get_driver_instance(node_instance.asset.ned_id)
        _print_rendered(ned.render(config, node_instance.asset))
    else:
        _, config = _fetch_desired_config(sdk, node)
        t2 = time.time()
        _print_parsed_config(config.model_dump(), path=path, format=format, title=f"Desired config — {node}")
        t3 = time.time()

    typer.echo(f"[debug] sdk init: {t1-t0:.2f}s, fetch: {t2-t1:.2f}s, render: {t3-t2:.2f}s")


@config_show_app.command("observed")
def config_show_observed(
    ctx: typer.Context,
    node: str = typer.Argument(help="Node ID or hostname"),
    render: bool = typer.Option(False, "--render", help="Show rendered device config"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Drill into section, e.g. system.ntp, interfaces"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Show observed (backup) config."""
    sdk = get_sdk(ctx.obj.get_active_context())
    node_id = _resolve_node_id(sdk, node) if not node.isdigit() else node
    outputformat = "rendered" if render else "parsed"
    observed = _get_latest_observed_config(sdk, node_id, outputformat)

    if not observed:
        typer.echo("No observed config found.")
        raise typer.Exit(1)

    content = observed.get("content") if isinstance(observed, dict) else None
    if content is None:
        typer.echo("Observed config has no content.")
        raise typer.Exit(1)

    if render:
        _print_rendered(_decode_config_content(content))
    else:
        _print_parsed_config(content, path=path, format=format, title=f"Observed config — {node}")


# ── Config diff commands ────────────────────────────────────────

@config_diff_app.command("plan")
def config_diff_plan(
    ctx: typer.Context,
    node: str = typer.Argument(help="Node ID or hostname"),
    format: str = typer.Option(
        "tree", "--format", "-f",
        help="Output format: tree, compact, flat, summary, json, commands",
    ),
    max_depth: Optional[int] = typer.Option(None, "--max-depth", "-d", help="Max depth for tree view"),
    no_values: bool = typer.Option(False, "--no-values", help="Hide values in tree view"),
):
    """Show planned diff between observed and desired config."""
    sdk = get_sdk(ctx.obj.get_active_context())
    node_instance, desired_config = _fetch_desired_config(sdk, node)
    node_id = str(node_instance.id) if hasattr(node_instance, 'id') and node_instance.id else node

    observed_raw = _get_latest_observed_config(sdk, node_id, "parsed").get("content")
    observed_config = ComposedConfiguration(**observed_raw)

    diff = sdk.differ.diff(observed_config=observed_config, desired_config=desired_config)

    if format == "json":
        print(json.dumps(diff.model_dump(mode="python"), indent=4, default=str))
    elif format == "summary":
        print_diff_summary(diff)
    elif format == "tree":
        print_diff_tree(diff, max_depth=max_depth, show_values=not no_values)
    elif format == "compact":
        print_diff_compact(diff)
    elif format == "flat":
        print_diff_flat(diff)
    elif format == "commands":
        ned = sdk.neds.get_driver_instance(node_instance.asset.ned_id)
        print(ned.render_patch(diff, node_instance))
    else:
        typer.echo(f"Unknown format: {format}")
        typer.echo("Available formats: tree, compact, flat, summary, json, commands")


@config_diff_app.command("apply")
def config_diff_apply(
    ctx: typer.Context,
    node: str = typer.Argument(help="Node ID or hostname"),
):
    """Compute diff and apply config patch to device."""
    sdk = get_sdk(ctx.obj.get_active_context())
    node_instance, desired_config = _fetch_desired_config(sdk, node)
    node_id = str(node_instance.id) if hasattr(node_instance, 'id') and node_instance.id else node

    observed_raw = _get_latest_observed_config(sdk, node_id, "parsed").get("content")
    observed_config = ComposedConfiguration(**observed_raw)

    diff = sdk.differ.diff(observed_config=observed_config, desired_config=desired_config)
    ned = sdk.neds.get_driver_instance(node_instance.asset.ned_id)

    commands = ned.render_patch(diff, node_instance)
    print_commands_box(commands, node_id)

    if not typer.confirm("Are you sure you want to apply the config above?"):
        raise typer.Exit()

    connection = _get_connection(sdk, node_id)
    ned.apply_patch(diff, node_instance, connection[0].get("target_ip"))


# ── Config display helpers ──────────────────────────────────────

def _print_rendered(text: str):
    """Print rendered device config with syntax highlighting."""
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    console = Console()
    syntax = Syntax(text, "cisco", theme="monokai", line_numbers=True, word_wrap=True)
    console.print(Panel(syntax, border_style="dim"))


def _navigate_path(data: dict, path: str):
    """Navigate into a nested dict by dotted path. Returns (value, resolved_path)."""
    parts = path.split(".")
    current = data
    resolved = []
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
            resolved.append(part)
        else:
            available = list(current.keys()) if isinstance(current, dict) else []
            typer.echo(f"Path '{'.'.join(resolved + [part])}' not found.")
            if available:
                typer.echo(f"Available keys: {', '.join(available)}")
            raise typer.Exit(1)
    return current


def _is_attribute_value(data) -> bool:
    """Check if a dict looks like an AttributeValue ({value: ..., metadata: ...})."""
    return isinstance(data, dict) and "value" in data and len(data) <= 3


def _unwrap_av(data):
    """Unwrap an AttributeValue, returning (value, source)."""
    value = data.get("value")
    metadata = data.get("metadata", {})
    source = metadata.get("value_source") if isinstance(metadata, dict) else None
    return value, source


def _count_components(data) -> int:
    """Count meaningful items in a config section."""
    if not isinstance(data, dict):
        return 0 if data is None else 1
    if _is_attribute_value(data):
        return 1
    count = 0
    for v in data.values():
        if isinstance(v, dict):
            if _is_attribute_value(v):
                count += 1
            elif v:
                count += len(v)
        elif isinstance(v, list):
            count += len(v)
        elif v is not None:
            count += 1
    return count


def _print_parsed_config(data: dict, path: Optional[str], format: str, title: str):
    """Display parsed config with AttributeValue awareness."""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    if format == "json":
        section = _navigate_path(data, path) if path else data
        console.print_json(json.dumps(section, indent=2, default=str))
        return

    if path:
        section = _navigate_path(data, path)
        # Single AttributeValue
        if _is_attribute_value(section):
            value, source = _unwrap_av(section)
            console.print(f"[bold]{path}[/bold] = {value}", highlight=False)
            if source and source != "concrete":
                console.print(f"  [dim]source: {source}[/dim]")
            return
        # Dict of AttributeValues (e.g. system.config)
        if isinstance(section, dict) and section and all(_is_attribute_value(v) for v in section.values() if isinstance(v, dict) and v):
            _print_attributes_table(console, section, title=path)
            return
        # Container with named entries (e.g. interfaces, ntp.servers)
        if isinstance(section, dict):
            _print_config_section(console, section, path)
            return
        # Fallback
        console.print_json(json.dumps(section, indent=2, default=str))
        return

    # Default: overview table
    table = Table(title=title, show_header=True)
    table.add_column("Section", style="bold cyan")
    table.add_column("Components", style="white", justify="right")
    table.add_column("Drill into", style="dim")

    for section_name, section_data in data.items():
        count = _count_components(section_data) if isinstance(section_data, dict) else (1 if section_data else 0)
        table.add_row(
            section_name,
            str(count),
            f"--path {section_name}" if count > 0 else "",
        )

    console.print(table)
    console.print("[dim]Use --path <section> to drill in, --format json for full dump, --render for device config[/dim]")


def _print_attributes_table(console, data: dict, title: str = ""):
    """Print a dict where values are AttributeValues as a clean table."""
    from rich.table import Table
    table = Table(title=title, show_header=True, title_style="bold", title_justify="left")
    table.add_column("Attribute", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")

    for key, val in data.items():
        if _is_attribute_value(val):
            value, source = _unwrap_av(val)
            table.add_row(key, str(value) if value is not None else "", source or "concrete")
        elif val is None:
            table.add_row(key, "", "")
        else:
            table.add_row(key, str(val), "")

    console.print(table)


def _print_config_section(console, data: dict, path: str):
    """Print a config section, handling containers and nested AttributeValues."""
    from rich.table import Table

    # Check if entries are named components (e.g. interfaces, ntp.servers)
    for entry_name, entry_data in data.items():
        if not isinstance(entry_data, dict):
            continue

        # Collect AttributeValue fields from this entry
        attrs = {}
        nested = {}
        for k, v in entry_data.items():
            if _is_attribute_value(v):
                attrs[k] = v
            elif k in ("metadata", "identity_fields"):
                continue
            elif isinstance(v, dict) and v:
                nested[k] = v
            elif v is not None:
                attrs[k] = {"value": v}

        if attrs:
            _print_attributes_table(console, attrs, title=f"{path}.{entry_name}")

        for sub_name, sub_data in nested.items():
            sub_path = f"{path}.{entry_name}.{sub_name}"
            if isinstance(sub_data, dict) and sub_data:
                console.print(f"\n[bold dim]{sub_path}[/bold dim] ({len(sub_data)} entries)")
            else:
                console.print(f"\n[bold dim]{sub_path}[/bold dim]")


# ── Util ────────────────────────────────────────────────────────

def _flatten_node(node) -> dict:
    """Flatten NodeResponse into a single-level dict for display."""
    data = node.model_dump() if hasattr(node, "model_dump") else dict(node)
    asset = data.pop("asset", {}) or {}
    logical_node = data.pop("logical_node", {}) or {}

    flat = {
        "id": data.get("id"),
        "hostname": logical_node.get("hostname"),
        "site": logical_node.get("site"),
        "role": logical_node.get("role"),
        "status": data.get("status"),
        "vendor": asset.get("vendor"),
        "os": asset.get("os"),
        "os_version": asset.get("os_version"),
        "hardware_model": asset.get("hardware_model"),
        "serial_number": asset.get("serial_number"),
        "ned_id": asset.get("ned_id"),
        "logical_node_id": data.get("logical_node_id"),
        "asset_ref_id": data.get("asset_ref_id"),
        "asset_ref_type": data.get("asset_ref_type"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }
    return flat


def _resolve_node(sdk, identifier: str):
    """Resolve a node by ID or hostname. Returns NodeResponse or exits."""
    # Try as numeric ID first
    if identifier.isdigit():
        node = sdk.node_instances.get(identifier)
        if node:
            return node

    # Search by hostname
    result = sdk.node_instances.query(hostname=identifier)
    if len(result) == 1:
        return sdk.node_instances.get(result.items[0].id)
    elif len(result) > 1:
        typer.echo(f"Multiple nodes match hostname '{identifier}':")
        from acex_cli.output import display_list
        display_list(result, columns=["id", "hostname", "site", "status"], title="")
        typer.echo("Use the ID to specify which node.")
        raise typer.Exit(1)

    typer.echo(f"Node '{identifier}' not found.")
    raise typer.Exit(1)


def _resolve_node_id(sdk, identifier: str) -> str:
    """Resolve to a node ID string. For use in config commands."""
    if identifier.isdigit():
        return identifier
    # query returns NodeListItem which always has id
    result = sdk.node_instances.query(hostname=identifier)
    if len(result) == 1:
        return str(result.items[0].id)
    elif len(result) > 1:
        typer.echo(f"Multiple nodes match hostname '{identifier}':")
        from acex_cli.output import display_list
        display_list(result, columns=["id", "hostname", "site", "status"], title="")
        typer.echo("Use the ID to specify which node.")
        raise typer.Exit(1)
    typer.echo(f"Node '{identifier}' not found.")
    raise typer.Exit(1)


def _compact(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}
