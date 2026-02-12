import base64
import difflib
import json
from enum import Enum
from typing import Optional

import requests
import typer

from acex_cli.sdk import get_sdk
from acex_cli.print_utils import print_list_table, print_object
from acex_client.models.generated_models import Node

from acex_devkit.models.composed_configuration import ComposedConfiguration


def _get_ned(asset_name: str):
    print("Fixar nedden")


#### REMOVE THESE AND USE SDK WHEN IMPLEMENTED 
def _request_get(sdk, path: str, params: Optional[dict] = None) -> requests.Response:
    verify = getattr(getattr(sdk, "rest", None), "verify", True)
    url = f"{sdk.api_url}{path}"
    response = requests.get(url, params=params, verify=verify)
    response.raise_for_status()
    return response


def _get_rendered_config(sdk, node_id: str) -> str:
    response = _request_get(sdk, f"/inventory/node_instances/{node_id}/config")
    return response.text


def _get_latest_observed_config(sdk, node_id: str, output: str) -> dict:
    response = _request_get(sdk, f"/operations/device_configs/{node_id}/latest?output={output}")
    return response.json()


def _get_observed_config_by_hash(sdk, node_id: str, config_hash: str) -> dict:
    response = _request_get(sdk, f"/operations/device_configs/{node_id}/{config_hash}")
    return response.json()


def _list_observed_config_hashes(sdk, node_id: str) -> list:
    response = _request_get(sdk, f"/operations/device_configs/{node_id}")
    return response.json()


def _get_observed_config_before(sdk, node_id: str, point_in_time: str) -> Optional[dict]:
    response = _request_get(
        sdk,
        f"/operations/device_configs/{node_id}",
        params={"point_in_time": point_in_time, "limit": 1},
    )
    items = response.json()
    if not items:
        return None
    config_hash = items[0].get("hash")
    if not config_hash:
        return None
    return _get_observed_config_by_hash(sdk, node_id, config_hash)


def _decode_config_content(content: str) -> str:
    return base64.b64decode(content).decode("utf-8", errors="replace")
#### REMOVE THESE AND USE SDK WHEN IMPLEMENTED 



app = typer.Typer(help="Node resource commands")
# NODE RESOURCE COMMANDS: 
@app.command()
def list(ctx: typer.Context):
    """List all nodes."""
    sdk = get_sdk(ctx.obj.get_active_context())
    nodes = sdk.node_instances.get_all()
    if not nodes:
        typer.echo("No nodes found.")
        return
    
    print_list_table(nodes, pydantic_class=Node, title="Node Instances")

@app.command()
def show(ctx: typer.Context, node_id: str):
    """Show details for a logical node."""
    sdk = get_sdk(ctx.obj.get_active_context())
    node = sdk.node_instances.get(node_id)

    print_object(node, pydantic_class=Node, title=f"Node {node_id} details")
####################################################################

# NODE CONFIG COMMANDS: #
config_app = typer.Typer(help="Node configuration commands")

## node config show|diff
config_show_app = typer.Typer(help="Configuration diff commands")
config_diff_app = typer.Typer(help="Configuration diff commands")

app.add_typer(config_app, name="config")
config_app.add_typer(config_diff_app, name="diff")
config_app.add_typer(config_show_app, name="show")

####################################################################

# NODE CONFIG SHOW COMMANDS
@config_show_app.command("desired")
def desired_config(
    ctx: typer.Context,
    node_id: str,
    render: bool = False,
    path: str = None,
):
    """Show desired config (rendered or JSON data model)."""
    sdk = get_sdk(ctx.obj.get_active_context())

    node_instance = sdk.node_instances.get(node_id)
    if not node_instance:
        typer.echo("Node instance not found.")
        return

    logical_node = sdk.logical_nodes.get(node_instance.logical_node_id)
    if not logical_node:
        typer.echo("Logical node not found.")
        return

    configuration = getattr(logical_node, "configuration", None)
    if configuration is None:
        typer.echo("No desired configuration found.")
        return

    # dump to json
    config_dump = configuration.model_dump()

    # If path, select part of dump..
    # TODO: implement here.

    # If render, use renderer in sdk to render config
    if render:
        ned = sdk.neds.get_driver_instance(node_instance.asset.ned_id)
        rendered = ned.render(logical_node, node_instance.asset)
        typer.echo(rendered)
    else:
        typer.echo(json.dumps(config_dump, indent=2, default=str))


@config_show_app.command("observed")
def observed_config(
    ctx: typer.Context,
    node_id: str,
    render: bool = False,
    # path: str = None, # TODO: Implement this flag
    # config_hash: Optional[str] = typer.Option(
    #     None, "--hash", help="Fetch a specific backup by hash"
    # ),
):
    """Show observed (backup) config (rendered or JSON data object)."""
    sdk = get_sdk(ctx.obj.get_active_context())

    if render:
        outputformat = "rendered"
    else:
        outputformat = "parsed"
    observed = _get_latest_observed_config(sdk, node_id, outputformat)

    if not observed:
        typer.echo("No observed config found.")
        return

    content = observed.get("content") if isinstance(observed, dict) else None
    if content is None:
        typer.echo("Observed config has no content.")
        return

    if render:
        typer.echo(_decode_config_content(content))
    else:
        typer.echo(json.dumps(content, indent=2, default=str))

    # decoded = _decode_config_content(content)
    # typer.echo(decoded)

# TODO: IMPLEMENT observed-list

####################################################################

# NODE CONFIG DIFF COMMANDS

# TODO: IMPLEMENT HERE

@config_diff_app.command("apply")
def hej(
    ctx: typer.Context,
    node_id: str,
    format: str = typer.Option(
        "tree", "--format", "-f",
        help="Output format: tree, compact, flat, summary, json"
    ),
    max_depth: int = typer.Option(
        None, "--max-depth", "-d",
        help="Maximum depth to show in tree view"
    ),
    no_values: bool = typer.Option(
        False, "--no-values",
        help="Hide values in tree view (show only structure)"
    ),
):
    """Show diff between desired and observed config."""
    from acex_cli.diff_formatters import (
        print_diff_summary,
        print_diff_tree, 
        print_diff_compact,
        print_diff_flat
    )
    
    sdk = get_sdk(ctx.obj.get_active_context())
    differ = sdk.differ
    
    # Fetch observed config
    observed_config = _get_latest_observed_config(sdk, node_id, "parsed").get("content")
    observed_config = ComposedConfiguration(**observed_config)


    # Fetch desired config
    node_instance = sdk.node_instances.get(node_id)
    if not node_instance:
        typer.echo("Node instance not found.")
        return

    logical_node = sdk.logical_nodes.get(node_instance.logical_node_id)
    if not logical_node:
        typer.echo("Logical node not found.")
        return

    desired_config = getattr(logical_node, "configuration", None)
    if desired_config is None:
        typer.echo("No desired configuration found.")
        return

    diff = differ.diff(observed_config=observed_config, desired_config=desired_config)

    # Display diff based on format
    if format == "json":
        # Use Python mode to avoid Pydantic serialization warnings with AttributeValue types
        print(json.dumps(diff.model_dump(mode="python"), indent=4, default=str))
    elif format == "summary":
        print_diff_summary(diff)
    elif format == "tree":
        print_diff_tree(diff, max_depth=max_depth, show_values=not no_values)
    elif format == "compact":
        print_diff_compact(diff)
    elif format == "flat":
        print_diff_flat(diff)
    else:
        typer.echo(f"Unknown format: {format}")
        typer.echo("Available formats: tree, compact, flat, summary, json")


# acex node config diff {from} {to} 

####################################################################











# @config_diff_app.command("observed")
# def observed_config_diff(
#     ctx: typer.Context,
#     node_id: str,
#     diff_from: Optional[str] = typer.Option(
#         None, "--from-hash", help="Diff from this backup hash"
#     ),
#     diff_to: Optional[str] = typer.Option(
#         None, "--to-hash", help="Diff to this backup hash"
#     ),
#     diff_from_time: Optional[str] = typer.Option(
#         None,
#         "--from-time",
#         help="Diff from latest backup at or before this timestamp (ISO 8601)",
#     ),
#     diff_to_time: Optional[str] = typer.Option(
#         None,
#         "--to-time",
#         help="Diff to latest backup at or before this timestamp (ISO 8601)",
#     ),
# ):
#     """Diff observed (backup) configs between two hashes."""
#     sdk = get_sdk(ctx.obj.get_active_context())

#     using_hashes = diff_from is not None and diff_to is not None
#     using_times = diff_from_time is not None and diff_to_time is not None

#     if using_hashes and using_times:
#         typer.echo("Use either --from-hash/--to-hash or --from-time/--to-time, not both.")
#         raise typer.Exit(code=2)

#     if not using_hashes and not using_times:
#         typer.echo("Provide --from-hash/--to-hash or --from-time/--to-time.")
#         raise typer.Exit(code=2)

#     if using_times:
#         left = _get_observed_config_before(sdk, node_id, diff_from_time)
#         right = _get_observed_config_before(sdk, node_id, diff_to_time)
#         left_hash = left.get("hash") if isinstance(left, dict) else None
#         right_hash = right.get("hash") if isinstance(right, dict) else None
#         from_label = (
#             f"{node_id}:observed@{diff_from_time}"
#             f"{f'#{left_hash}' if left_hash else ''}"
#         )
#         to_label = (
#             f"{node_id}:observed@{diff_to_time}"
#             f"{f'#{right_hash}' if right_hash else ''}"
#         )
#     else:
#         left = _get_observed_config_by_hash(sdk, node_id, diff_from)
#         right = _get_observed_config_by_hash(sdk, node_id, diff_to)
#         from_label = f"{node_id}:{diff_from}"
#         to_label = f"{node_id}:{diff_to}"

#     if not left or not right:
#         typer.echo("Observed config not found for one or both inputs.")
#         return

#     left_content = left.get("content") if isinstance(left, dict) else None
#     right_content = right.get("content") if isinstance(right, dict) else None

#     if left_content is None or right_content is None:
#         typer.echo("Observed config content missing for one or both hashes.")
#         return

#     left_text = _decode_config_content(left_content).splitlines(keepends=True)
#     right_text = _decode_config_content(right_content).splitlines(keepends=True)

#     diff = difflib.unified_diff(
#         left_text,
#         right_text,
#         fromfile=from_label,
#         tofile=to_label,
#     )
#     typer.echo("".join(diff))


# @config_diff_app.command("desired-observed")
# def desired_observed_diff(
#     ctx: typer.Context,
#     node_id: str,
#     config_hash: Optional[str] = typer.Option(
#         None, "--hash", help="Diff against a specific observed backup hash"
#     ),
#     point_in_time: Optional[str] = typer.Option(
#         None,
#         "--time",
#         help="Diff against latest observed backup at or before this timestamp (ISO 8601)",
#     ),
# ):
#     """Diff desired config against observed (backup) config."""
#     sdk = get_sdk(ctx.obj.get_active_context())

#     if config_hash and point_in_time:
#         typer.echo("Use either --hash or --time, not both.")
#         raise typer.Exit(code=2)

#     desired = _get_rendered_config(sdk, node_id)
#     if config_hash:
#         observed = _get_observed_config_by_hash(sdk, node_id, config_hash)
#         observed_label = f"{node_id}:observed@{config_hash}"
#     elif point_in_time:
#         observed = _get_observed_config_before(sdk, node_id, point_in_time)
#         observed_label = f"{node_id}:observed@{point_in_time}"
#     else:
#         observed = _get_latest_observed_config(sdk, node_id)
#         observed_label = f"{node_id}:observed"

#     if not observed:
#         typer.echo("No observed config found.")
#         return

#     content = observed.get("content") if isinstance(observed, dict) else None
#     if content is None:
#         typer.echo("Observed config has no content.")
#         return

#     observed_text = _decode_config_content(content)
#     diff = difflib.unified_diff(
#         desired.splitlines(keepends=True),
#         observed_text.splitlines(keepends=True),
#         fromfile=f"{node_id}:desired",
#         tofile=observed_label,
#     )
#     typer.echo("".join(diff))


# @config_app.command("observed-list")
# def observed_config_list(ctx: typer.Context, node_id: str):
#     """List observed config backups for a node instance."""
#     sdk = get_sdk(ctx.obj.get_active_context())
#     backups = _list_observed_config_hashes(sdk, node_id)
#     if not backups:
#         typer.echo("No observed config backups found.")
#         return

#     print_list_table(
#         backups,
#         columns=["id", "hash", "created_at", "node_instance_id"],
#         title=f"Observed config backups for node {node_id}",
#     )

