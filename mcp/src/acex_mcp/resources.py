"""What ACE-X is, in the words the tools use.

This is the authoritative description of the domain for any client. An external
client (Claude Desktop, Cursor) has no ACE-X system prompt, so if it is not here
the client does not know it.

The entity reference is generated from the actual Pydantic models rather than
written by hand. Hand-written field lists are how the previous implementation
came to promise fields that did not exist.
"""

from datetime import UTC, datetime
from typing import Any, get_args, get_origin

from acex_devkit.models.asset import AssetResponse
from acex_devkit.models.config_snapshot import ConfigSnapshotListItem
from acex_devkit.models.lldp_neighbor import LldpNeighborResponse
from acex_devkit.models.logical_node import LogicalNodeResponse
from acex_devkit.models.node_response import NodeListItem, NodeResponse
from acex_devkit.models.region import RegionResponse
from acex_devkit.models.site import SiteResponse
from fastmcp import FastMCP
from pydantic import BaseModel

GLOSSARY = """\
ACE-X GLOSSARY
==============

CONFIGURATION — three distinct things. Conflating them produces wrong answers.

  desired    The configuration ACE-X intends the device to have. ACE-X is the
             source of truth for it. Tool: get_desired_config.

  observed   A configuration snapshot actually collected from the device,
             stamped with collected_at. Versioned over time, so any past moment
             can be read. Tool: get_observed_config.

  running    What is on the device right now. NOT retrievable through ACE-X
             yet — collection agents poll on a schedule and there is no
             on-demand read. get_running_config exists only to say so and offer
             the newest observed snapshot instead.

WHAT USERS SAY, AND WHAT THEY MEAN

  "running config", "actual config", "live config", "what's on the box"
      → normally the latest observed snapshot. Answer with it, but say when it
        was collected. Never imply it was read from the device just now.
  "intended", "target", "source of truth", "what it should be"
      → desired.
  "compiled", "rendered"
      → desired, rendered to device commands. That is what get_desired_config
        already returns.
  "drift", "out of sync", "compliant"
      → the difference between desired and the latest observed: get_config_drift.

The translation runs one way only. Understand these words as input; reply in
ACE-X's own terms — desired and observed — so your language matches what the
user sees in the ACE-X interface.

ENTITIES

  node        A deployed device: a desired configuration bound to hardware.
              What operators mean by "switch", "router", "device". Every tool
              addresses nodes by node_id.
  asset       A physical chassis record, independent of any configuration.
              Exists whether or not it is deployed.
  logical     The desired-configuration template a node is built from. Its id
    node      appears on a node for traceability; no tool requires it.
  site        A physical location.
  region      A logical grouping of sites.
  NED         The vendor driver used to render and parse a device's config.
              A node whose asset has no NED cannot have its desired config
              rendered.

TIMESTAMPS

  All timestamps are UTC. Snapshot times are stored without a zone offset and
  are UTC; a naive timestamp passed to a tool is read as UTC. To answer a
  question about a wall-clock time in someone's local zone, convert to UTC
  first, or pass an explicit offset.
"""

WRITE_ACCESS = """\
WHAT THIS SERVER CANNOT DO
==========================

Every tool here is read-only. This server cannot change a configuration, push
anything to a device, or create or delete records. ACE-X has no config-push
path at all — configuration reaches devices by other means entirely.

If a user asks you to change something, say plainly that you can read and
analyse ACE-X but not modify it, and describe what they would need to do.
Never claim to have made a change, and never imply a change is pending.
"""


def _type_name(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is not None:
        args = [a for a in get_args(annotation) if a is not type(None)]
        names = " | ".join(_type_name(a) for a in args)
        if origin is list:
            return f"list[{names}]"
        if origin is dict:
            return "object"
        return names or "any"
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return annotation.__name__
        return annotation.__name__
    return str(annotation)


def _describe(model: type[BaseModel]) -> str:
    lines = []
    for name, field in model.model_fields.items():
        optional = "" if field.is_required() else " (optional)"
        lines.append(f"  {name}: {_type_name(field.annotation)}{optional}")
    return "\n".join(lines)


def _entity_reference() -> str:
    sections = [
        ("Node — one row of find_nodes()", NodeListItem),
        ("Node — get_node() source record", NodeResponse),
        ("Logical node (the desired-config template)", LogicalNodeResponse),
        ("Asset (physical hardware)", AssetResponse),
        ("Site", SiteResponse),
        ("Region", RegionResponse),
        ("Configuration snapshot (metadata only)", ConfigSnapshotListItem),
        ("LLDP neighbour", LldpNeighborResponse),
    ]
    out = [
        "ACE-X ENTITY REFERENCE",
        "======================",
        "",
        "Generated from the live backend models, so it cannot drift from reality.",
        "Tool responses reshape these — they rename ids to node_id/asset_id and",
        "flatten nested records — so treat this as the underlying data model,",
        "not as the exact shape a tool returns.",
        "",
    ]
    for title, model in sections:
        out.append(title)
        out.append("-" * len(title))
        out.append(_describe(model))
        out.append("")
    return "\n".join(out)


def register(mcp: FastMCP) -> None:

    @mcp.resource("acex://glossary", name="ACE-X glossary", mime_type="text/plain")
    def glossary() -> str:
        """The vocabulary of ACE-X — desired vs observed vs running, and the
        entities the tools address. Read this before answering configuration
        questions."""
        return GLOSSARY

    @mcp.resource("acex://entities", name="ACE-X entity reference", mime_type="text/plain")
    def entities() -> str:
        """Field-level reference for ACE-X entities, generated from the backend's
        own models."""
        return _entity_reference()

    @mcp.resource("acex://capabilities", name="ACE-X MCP capabilities", mime_type="text/plain")
    def capabilities() -> str:
        """What this server can and cannot do. It is read-only."""
        return WRITE_ACCESS

    @mcp.resource("acex://now", name="Current server time", mime_type="text/plain")
    def now() -> str:
        """The current UTC time, for resolving relative dates like "yesterday"
        or "the day before yesterday at 19:00" into the ISO timestamps the
        tools accept."""
        current = datetime.now(UTC)
        return (
            f"Current time (UTC): {current.replace(microsecond=0, tzinfo=None).isoformat()}\n"
            f"Weekday: {current.strftime('%A')}\n"
            "\n"
            "Use this to turn a relative date into an ISO timestamp for the `at` "
            "and `before` arguments. All ACE-X timestamps are UTC."
        )
