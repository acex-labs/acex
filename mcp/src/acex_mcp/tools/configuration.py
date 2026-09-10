"""Configuration: what a node should be, what it was last seen to be, and the gap.

ACE-X distinguishes three things, and conflating them produces wrong answers:

  desired   — the intended configuration. ACE-X is the source of truth for it.
  observed  — a snapshot actually collected from the device, stamped with
              `collected_at`. Versioned, so any past point in time can be read.
  running   — what is on the device *right now*. Not retrievable yet; see
              get_running_config.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..backend import call, client, get_json
from ..config import settings
from ..text import prepare

READ_ONLY: dict[str, Any] = {"readOnlyHint": True, "openWorldHint": False}

#: Equal lines kept either side of a change when rendering a snapshot diff.
_DIFF_CONTEXT = 3

#: Cap on component changes returned by get_config_drift before summarising.
_MAX_DRIFT_ROWS = 60

#: Gap between a requested point in time and the snapshot actually in effect
#: beyond which the answer needs to say so out loud.
_STALE_GAP = timedelta(hours=1)

#: The backend hands back this string instead of failing when a node's asset
#: has no NED driver installed. Passing it on as config text would be worse
#: than an error, so it is turned into one.
_NED_MISSING = "error: NED not found"


def _to_naive_utc(value: str) -> datetime:
    """Parse an ISO 8601 timestamp into the naive-UTC form the backend stores.

    Snapshot timestamps are persisted with `datetime.utcnow()`, i.e. naive UTC.
    A tz-aware input is converted; a naive input is taken to already be UTC.
    Getting this wrong silently returns the config from a different hour.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ToolError(
            f"Could not read '{value}' as a timestamp. Use ISO 8601 in UTC, "
            "e.g. '2026-09-08T19:00:00' or '2026-09-08T21:00:00+02:00'."
        ) from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _config_payload(text: str, section: str | None) -> dict:
    shaped = prepare(text, section=section, max_chars=settings.max_config_chars)
    payload: dict[str, Any] = {
        "config": shaped.text,
        "total_lines": shaped.total_lines,
        "returned_lines": shaped.returned_lines,
        "truncated": shaped.truncated,
    }
    if section:
        payload["section"] = section
        if not shaped.matched:
            payload["note"] = (
                f"Nothing in this config matches '{section}'. The config itself is "
                f"{shaped.total_lines} lines; either the term is absent or it is spelled "
                "differently here. Try a broader term, or omit `section` to see everything."
            )
    return payload


def _render_unified(entries: list[Any]) -> str:
    """Render diff entries as unified-diff text with limited context.

    Returning every equal line would put a whole config into the model's
    context to convey a handful of changes; unified diff is also the format
    models read most reliably.
    """
    changed = [i for i, e in enumerate(entries) if e.type in ("add", "remove")]
    if not changed:
        return ""

    keep: set[int] = set()
    for i in changed:
        for j in range(max(0, i - _DIFF_CONTEXT), min(len(entries), i + _DIFF_CONTEXT + 1)):
            keep.add(j)

    out: list[str] = []
    previous = None
    for i in sorted(keep):
        if previous is not None and i > previous + 1:
            out.append("@@")
        entry = entries[i]
        marker = {"add": "+", "remove": "-"}.get(entry.type, " ")
        out.append(f"{marker}{entry.text}")
        previous = i
    return "\n".join(out)


def _drift_rows(changes: list[dict], op: str) -> list[dict]:
    rows = []
    for change in changes:
        row = {
            "op": op,
            "path": "/".join(str(p) for p in change.get("path", [])),
            "component": change.get("component_name"),
        }
        attributes = change.get("changed_attributes") or []
        if attributes:
            row["attributes"] = [
                {
                    "name": attribute.get("attribute_name"),
                    "desired": attribute.get("after"),
                    "observed": attribute.get("before"),
                }
                for attribute in attributes
            ]
        rows.append(row)
    return rows


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    async def get_desired_config(node_id: int, section: str | None = None) -> dict:
        """Get a node's DESIRED configuration, rendered as device commands.

        This is what ACE-X intends the device to be configured as — the source
        of truth, not a reading from the device. It is rendered through the
        node's vendor driver, so it is directly comparable with an observed
        config from the same device.

        Args:
            node_id: From find_nodes().
            section: Keep only matching config blocks, e.g. "GigabitEthernet1/0/49",
                "vlan 100", "ntp". Case-insensitive substring; enclosing block
                headers and indented children of a match are kept with it.
                Use this whenever the question is about one interface, VLAN or
                feature rather than the whole config.

        For what the device was actually last seen running, use
        get_observed_config(). For the difference, use get_config_drift().
        """
        text = await call(
            client().inventory.node_instances.configuration_desired,
            id=node_id,
            doing=f"rendering the desired config for node {node_id}",
        )
        if not text or text.strip() == _NED_MISSING:
            raise ToolError(
                f"Node {node_id} has no usable vendor driver (NED), so its desired configuration "
                "cannot be rendered. Its hardware record is probably missing a ned_id — check "
                "get_node(node_id) and report that rather than guessing at the config."
            )
        return {"node_id": node_id, "kind": "desired", **_config_payload(text, section)}

    @mcp.tool(annotations=READ_ONLY)
    async def get_observed_config(
        node_id: int,
        at: str | None = None,
        snapshot_id: int | None = None,
        section: str | None = None,
    ) -> dict:
        """Get a configuration snapshot collected from a node.

        An observed config is what was actually read off the device and stored,
        stamped with `collected_at`. When someone asks for the "running
        config", this is normally what they want — but say which snapshot it is
        and when it was collected, because it is not a live reading.

        Args:
            node_id: From find_nodes().
            at: Return the snapshot that was in effect at this moment, for
                questions like "how was it configured the day before yesterday
                at 19:00". ISO 8601; naive timestamps are read as UTC. The
                snapshot returned may have been collected well before `at` —
                compare `collected_at` with `requested_at` in the response and
                state the real collection time.
            snapshot_id: A specific snapshot from list_observed_configs().
            section: Keep only matching config blocks — see get_desired_config.

        Defaults to the most recent snapshot. `at` and `snapshot_id` are
        alternative ways of picking one; do not pass both.
        """
        if at and snapshot_id:
            raise ToolError("Pass either `at` or `snapshot_id`, not both — they are two ways of picking one snapshot.")

        nodes = client().inventory.node_instances
        requested_at: datetime | None = None

        if snapshot_id is not None:
            snapshot = await call(
                nodes.get_observed, node_id, snapshot_id, doing=f"reading snapshot {snapshot_id} of node {node_id}"
            )
        elif at:
            requested_at = _to_naive_utc(at)
            candidates = await call(
                nodes.list_observed,
                id=node_id,
                point_in_time=requested_at.isoformat(),
                limit=1,
                doing=f"finding the snapshot in effect for node {node_id} at {at}",
            )
            if not candidates:
                earliest = await call(
                    nodes.list_observed, id=node_id, limit=1, doing=f"listing snapshots for node {node_id}"
                )
                if not earliest:
                    raise ToolError(
                        f"No configuration snapshots exist for node {node_id} — either the node does not "
                        "exist or nothing has ever been collected from it. Check which with get_node(node_id)."
                    )
                raise ToolError(
                    f"No snapshot of node {node_id} exists at or before {at}. Nothing was collected from it "
                    "that early. Use list_observed_configs(node_id) to see the range that does exist."
                )
            snapshot = await call(
                nodes.get_observed,
                node_id,
                candidates[0].id,
                doing=f"reading the snapshot in effect for node {node_id} at {at}",
            )
            snapshot_id = candidates[0].id
        else:
            # The latest-snapshot endpoint returns content without an id, so
            # resolve the id first — otherwise the answer cannot be chained
            # into diff_observed_configs without a second lookup.
            newest = await call(
                nodes.list_observed, id=node_id, limit=1, doing=f"finding the latest snapshot of node {node_id}"
            )
            if not newest:
                raise ToolError(
                    f"No configuration snapshots exist for node {node_id} — either the node does not exist "
                    "or nothing has been collected from it yet. Check which with get_node(node_id), and say "
                    "so plainly rather than describing its desired config as if it were observed."
                )
            snapshot_id = newest[0].id
            snapshot = await call(
                nodes.get_observed, node_id, snapshot_id, doing=f"reading the latest config of node {node_id}"
            )

        if snapshot is None:
            raise ToolError(
                f"No configuration snapshots exist for node {node_id} — either the node does not exist "
                "or nothing has been collected from it yet. Check which with get_node(node_id), and say "
                "so plainly rather than describing its desired config as if it were observed."
            )

        content = snapshot.content if isinstance(snapshot.content, str) else str(snapshot.content)
        payload: dict[str, Any] = {
            "node_id": node_id,
            "kind": "observed",
            "snapshot_id": snapshot_id,
            "hash": snapshot.hash,
            "collected_at": snapshot.created_at,
            **_config_payload(content, section),
        }

        if requested_at is not None:
            payload["requested_at"] = requested_at
            collected = snapshot.created_at
            if collected.tzinfo is not None:
                collected = collected.astimezone(UTC).replace(tzinfo=None)
            gap = requested_at - collected
            if gap > _STALE_GAP:
                payload["note"] = (
                    f"This is the snapshot that was in effect at {at}, but it was collected "
                    f"{gap} earlier, at {snapshot.created_at}. Nothing was collected in between. "
                    "State the collection time — do not imply the config was captured at the requested moment."
                )
        return payload

    @mcp.tool(annotations=READ_ONLY)
    async def get_running_config(node_id: int) -> dict:
        """Read a node's live running configuration. NOT AVAILABLE YET.

        ACE-X cannot currently read a device on demand — collection agents poll
        on their own schedule, so the freshest thing that exists is the last
        observed snapshot. This tool exists to answer the question honestly
        rather than let a stale snapshot pass as a live reading.

        Args:
            node_id: From find_nodes().

        Tell the user ACE-X cannot read the device live right now, say how old
        the newest snapshot is, and offer it. Only call get_observed_config()
        if they want it — do not substitute it silently.
        """
        snapshots = await call(
            client().inventory.node_instances.list_observed,
            id=node_id,
            limit=1,
            doing=f"checking the newest snapshot of node {node_id}",
        )
        latest = (
            {"snapshot_id": snapshots[0].id, "collected_at": snapshots[0].created_at, "hash": snapshots[0].hash}
            if snapshots
            else None
        )
        return {
            "node_id": node_id,
            "available": False,
            "reason": (
                "Live device reads are not implemented. ACE-X collection agents poll on a schedule; "
                "there is no on-demand collection yet."
            ),
            "latest_observed": latest,
            "next_step": (
                "Tell the user ACE-X cannot read the device live, and offer the observed snapshot from "
                "collected_at instead. Call get_observed_config(node_id) only if they accept."
                if latest
                else (
                    "Tell the user ACE-X cannot read the device live, and that no snapshot has ever "
                    "been collected from it either."
                )
            ),
        }

    @mcp.tool(annotations=READ_ONLY)
    async def list_observed_configs(node_id: int, limit: int = 20, before: str | None = None) -> dict:
        """List a node's configuration snapshots, newest first.

        This is the node's configuration history — each entry is a point at
        which its config was collected and found to differ from the previous
        one. Use it to see when a device changed, and to get snapshot ids for
        diff_observed_configs() or get_observed_config(snapshot_id=...).

        Args:
            node_id: From find_nodes().
            limit: Maximum snapshots to return.
            before: Only snapshots at or before this ISO 8601 timestamp
                (naive is read as UTC). Use it to page back through history.
        """
        params: dict[str, Any] = {"id": node_id, "limit": limit}
        if before:
            params["point_in_time"] = _to_naive_utc(before).isoformat()
        snapshots = await call(
            client().inventory.node_instances.list_observed,
            doing=f"listing snapshots for node {node_id}",
            **params,
        )
        return {
            "node_id": node_id,
            "snapshots": [
                {"snapshot_id": item.id, "collected_at": item.created_at, "hash": item.hash} for item in snapshots
            ],
            "returned": len(snapshots),
        }

    @mcp.tool(annotations=READ_ONLY)
    async def diff_observed_configs(node_id: int, snapshot_a_id: int, snapshot_b_id: int) -> dict:
        """Compare two configuration snapshots of the same node.

        Answers "what changed on this device between these two points in time".
        Both ids come from list_observed_configs().

        Args:
            node_id: From find_nodes().
            snapshot_a_id: The older snapshot.
            snapshot_b_id: The newer snapshot.

        Returns `stats` plus `diff` as unified-diff text: lines starting with
        "-" were in A and are gone, "+" were added in B, "@@" marks skipped
        unchanged regions. Unchanged lines are omitted apart from a little
        context, so this is the change, not the whole config.
        """
        result = await call(
            client().inventory.node_instances.diff_observed,
            id=node_id,
            a=snapshot_a_id,
            b=snapshot_b_id,
            doing=f"diffing snapshots {snapshot_a_id} and {snapshot_b_id} of node {node_id}",
        )
        diff_text = _render_unified(result.diff)
        return {
            "node_id": node_id,
            "snapshot_a": {
                "snapshot_id": snapshot_a_id,
                "hash": result.config_a.hash,
                "collected_at": result.config_a.created_at,
            },
            "snapshot_b": {
                "snapshot_id": snapshot_b_id,
                "hash": result.config_b.hash,
                "collected_at": result.config_b.created_at,
            },
            "stats": {"added": result.stats.added, "removed": result.stats.removed, "unchanged": result.stats.equal},
            "diff": diff_text or "(no differences)",
        }

    @mcp.tool(annotations=READ_ONLY)
    async def get_config_drift(node_id: int) -> dict:
        """Compare a node's DESIRED configuration against its latest OBSERVED one.

        This is the drift question: has the device diverged from what ACE-X
        intends? The comparison is structural — per configuration component,
        not per text line — so it distinguishes a genuinely missing VLAN from a
        reordered line.

        Args:
            node_id: From find_nodes().

        Returns `summary` counts plus `changes`, each with:
          op         "missing"   in desired, absent from the device
                     "extra"     on the device, not in desired
                     "different" present in both, with differing attributes
          path       where in the configuration tree, e.g. "interfaces/Gi1/0/1"
          component  which component, e.g. "Vlan 100"
          attributes for "different": the desired and observed values

        Prefer this over fetching both configs and comparing them yourself.
        """
        # Raw JSON: the typed Diff model carries a `component_type: type[Any]`
        # field that cannot be validated back from JSON.
        raw = await get_json(
            f"/inventory/node_instances/{node_id}/configuration/intent_diff",
            doing=f"comparing desired and observed config for node {node_id}",
        )
        if not isinstance(raw, dict):
            raise ToolError(f"Could not compare configurations for node {node_id} — the backend returned no diff.")

        # The differ names its ops as a patch to apply *to the device*: ADD means
        # desired has a component the device lacks, REMOVE means the device has
        # one desired does not. Restated here from the device's point of view.
        rows = (
            _drift_rows(raw.get("added") or [], "missing")
            + _drift_rows(raw.get("removed") or [], "extra")
            + _drift_rows(raw.get("changed") or [], "different")
        )
        payload: dict[str, Any] = {
            "node_id": node_id,
            "summary": {
                "missing": len(raw.get("added") or []),
                "extra": len(raw.get("removed") or []),
                "different": len(raw.get("changed") or []),
                "components_desired": raw.get("total_desired"),
                "components_observed": raw.get("total_observed"),
            },
            "in_sync": not rows,
        }
        if len(rows) > _MAX_DRIFT_ROWS:
            payload["changes"] = rows[:_MAX_DRIFT_ROWS]
            payload["note"] = (
                f"{len(rows)} components differ; the first {_MAX_DRIFT_ROWS} are listed. "
                "Summarise the pattern rather than enumerating every one."
            )
        else:
            payload["changes"] = rows

        if not raw.get("total_observed"):
            # Everything then reads as "missing", which sounds like a bare
            # device rather than a comparison that could not be made.
            payload["note"] = (
                "No components could be parsed from this node's observed configuration, so this is not a "
                "usable comparison — every desired component appears 'missing' only because there is "
                "nothing to compare against. Its vendor driver may not parse this config, or nothing has "
                "been collected. Say that instead of reporting the device as unconfigured."
            )
        return payload
