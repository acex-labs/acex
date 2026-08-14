# Telemetry Agent (Telegraf sidecar)

## What this is

A thin polling sidecar (`src/acex_telemetry_agent/`) that keeps a local
`telegraf.conf` in sync with a `TelemetryAgent` resource on the ACEX backend.
It does **no rendering itself** — it just polls, downloads a pre-rendered
config, writes it atomically, and acks the revision it applied. All manifest
*building* logic lives server-side in `backend/src/acex/observability/`.

Runs as a container alongside Telegraf, sharing a config volume (see
`README.md` for env vars and the Docker setup).

## Sidecar poll loop (`agent.py`)

`TelemetryAgent.run()` loops forever on `poll_interval` (default 60s):

1. `GET /observability/agents/{id}` via `client.observability.agents.get()`
   → returns `config_revision`.
2. If this is the first run (no local file yet) or `config_revision` changed
   since the last loop iteration, fetch the rendered config with
   `GET /observability/agents/{id}/config` and write it to
   `TELEGRAF_CONFIG_PATH` via write-to-tmp + `os.replace` (atomic swap, no
   partial writes visible to Telegraf).
3. `POST /observability/agents/{id}/ack` with the revision just applied
   (`TelemetryAgentAck(config_revision=...)`), so the backend can track
   `acked_revision` / `acked_at` per agent.
4. Sleep, repeat. Any exception is caught, logged, and the loop continues
   (poll survives transient API/network failures).

Telegraf itself is expected to notice the file change externally (SIGHUP
from another sidecar, or `--watch-config`) — this agent only writes the file.

## Where the manifest actually comes from (backend)

The `TelemetryAgent` DB row (`backend/src/acex/observability/agents/models.py`)
stores identity + bookkeeping (`config_revision`, `acked_revision`, timestamps)
plus three link tables that define **scope**:

- `TelemetryAgentCapabilityLink` — which `TelemetryCapability` values
  (`icmp`, `mdt`, `snmp`, `snmp_trap`, `syslog_rfc5424` —
  `observability/capability.py`) this agent is allowed to collect.
- `TelemetryAgentNodeLink` — explicit node assignment.
- `TelemetryAgentMatchRule` — dynamic node matching by `site` / `role` /
  `region` / `vendor` / `os` / `status`, resolved against `Node` /
  `LogicalNode` / `Asset` / `SiteRegionAssignment` at read time (never
  materialized — see `_resolve_rule_nodes` in `manager.py`).
- `OutputDestination` — per-agent InfluxDB output blocks (v1/v2/v3), in
  addition to any backend-wide default outputs.

`TelemetryAgentManager` (`observability/agents/manager.py`) is the whole
CRUD + rendering surface, wired into FastAPI routes 1:1 in
`api/routers/observability_agents.py`. Mutating any of the above
(node link, rule, capability, output) calls `_bump_revision()`, which is
what makes the sidecar notice a change on its next poll.
`bump_revisions_for_node()` is also called from node lifecycle hooks so
agents whose match rules newly include/exclude a node get bumped even
without a direct edit to the agent itself.

### `get_config(id)` — building one manifest

1. Resolve capabilities (from `TelemetryAgentCapabilityLink`).
2. Resolve the node set: explicit links ∪ rule-matched nodes.
3. Load those `Node`s, their primary `ManagementConnection` IP, and their
   `LogicalNode` hostname.
4. Load the agent's `OutputDestination`s.
5. Stamp `last_config_poll` (every config fetch counts as a poll, not just
   the outer `get()`).
6. Delegate to `_render_telegraf_config(...)`.

### `_render_telegraf_config(...)` — assembling the TOML

1. Static `[agent]` header (hostname/interval/flush_interval — currently
   hardcoded, not user-configurable per agent).
2. **Inputs**: pulled from `TelemetryRegistry.for_telegraf_agent(node_ids, capabilities)`
   (see below), rendered by `observability/renderers/telegraf.py::render_inputs`.
3. **Outputs**: backend-wide default `InfluxDBOutput`s
   (`influxdb_settings.outputs`, set globally in `app.py`) first, then the
   agent's own `OutputDestination` rows — both rendered by the same
   `_render_output_block()` (duck-typed: works on the DB row or the
   in-memory default since both expose the same attribute names). Handles
   InfluxDB v1 (`influxdb`), v2 (`influxdb_v2`), and v3 (`influxdb_v3`)
   block shapes.

### `TelemetryRegistry` — intent → components (`observability/registry.py`)

The registry is **not persisted**. Every call to `.build()` reconstructs
the live set of `TelemetryComponent`s from current ACEX state (inventory +
config), so it can never drift from declared intent. It holds a list of
*providers* (`icmp_ping_provider`, `snmp_provider` by default, extensible
via `register_provider`) — each provider is a function that inspects the DB
and yields components.

`for_telegraf_agent(node_ids, capabilities)` is the gate a specific agent's
manifest is filtered through: a component is included only if
`component.capability` is in the agent's granted capability set, and (for
node-scoped components) `component.target_node()` is in the agent's
resolved node set. Cross-node components (`target_node() is None`) pass
through whenever their capability is granted.

### `TelemetryComponent` (`observability/components/base.py`)

Base class binding together telegraf collection, InfluxDB shape, and
Grafana tag identity for one measurable thing, so they can't drift apart:

- `capability` — gates which agents include it.
- `target_node()` — which node it belongs to (`None` = cross-node).
- `tags()` — tag set for the InfluxDB measurement / Grafana queries.
- `telegraf_input()` — `{"plugin", "config", "tags", "subtables"}` dict, or
  `None` if the component contributes nothing directly to telegraf.

Providers (`observability/providers.py`) share a `_per_node_provider()`
helper: it loads every `Node`, its `LogicalNode` (hostname/site), its
primary `ManagementConnection` IP, and site→region assignments, then
instantiates one component per node (or one per node per assigned region,
if the node's site maps to multiple regions).

Current concrete components:

- `IcmpPingTelemetry` (`icmp_ping.py`) — `[[inputs.ping]]`, capability `icmp`.
- `SnmpTelemetry` (`snmp.py`) — `[[inputs.snmp]]` polling uptime + sysName,
  capability `snmp`. Community string resolved per-node then per-site via
  `credential_manager`, falling back to `"public"`.

## Adding a new telemetry source

To add a new collectible metric end-to-end:

1. Add a `TelemetryCapability` value if it needs its own grant
   (`observability/capability.py`).
2. Add a `TelemetryComponent` subclass implementing `telegraf_input()`,
   `tags()`, `target_node()` (`observability/components/`).
3. Add or extend a provider that instantiates it from DB state
   (`observability/providers.py`), and register it in
   `TelemetryRegistry._register_defaults()` if it's a core default.
4. Grant the capability to the relevant `TelemetryAgent`(s) — the sidecar
   picks up the new inputs automatically on its next poll after the
   agent's `config_revision` is bumped.

No sidecar-side change is needed for new telemetry types — `agent.py` is
transport-agnostic; it just downloads whatever TOML the backend renders.
