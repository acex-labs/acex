"""
Standard dashboard definitions, generated from the TelemetryRegistry.

Each function takes a TelemetryRegistry and returns a dashboard dict (or
None if there are no relevant components and the dashboard would be empty).
"""

from acex.observability.capability import TelemetryCapability
from acex.observability.components.icmp_ping import IcmpPingTelemetry
from acex.observability.components.snmp import SnmpTelemetry
from acex.observability.registry import TelemetryRegistry
from acex.observability.renderers.grafana.builder import (
    bargauge_panel,
    grid_pos,
    influxql_target,
    make_dashboard,
    query_variable,
    stat_panel,
    state_timeline_panel,
    timeseries_panel,
)

# Threshold steps for percent_packet_loss colouring (state timeline + loss bars).
LOSS_THRESHOLDS = [
    {"color": "green", "value": None},
    {"color": "yellow", "value": 1},
    {"color": "orange", "value": 25},
    {"color": "red", "value": 75},
]

# Threshold steps for round-trip latency in ms.
LATENCY_THRESHOLDS = [
    {"color": "green", "value": None},
    {"color": "yellow", "value": 50},
    {"color": "orange", "value": 150},
    {"color": "red", "value": 500},
]

# Threshold steps for uptime in seconds: a short uptime means the device restarted lately.
UPTIME_THRESHOLDS = [
    {"color": "red", "value": None},
    {"color": "orange", "value": 3600},
    {"color": "yellow", "value": 86400},
    {"color": "green", "value": 604800},
]

# Threshold steps for the number of SNMP samples that arrived in a bucket.
POLLED_THRESHOLDS = [
    {"color": "red", "value": None},
    {"color": "green", "value": 1},
]

# `sysUpTime` is TimeTicks, hundredths of a second.
TICKS_PER_SECOND = 100
TICKS_PER_DAY = TICKS_PER_SECOND * 86400


def icmp_overview_dashboard(registry: TelemetryRegistry) -> dict | None:
    """ICMP ping overview with site/node filters, rollups, top-N and reachability."""
    pings: list[IcmpPingTelemetry] = registry.by_kind(IcmpPingTelemetry.kind)
    if not pings:
        return None

    measurement = IcmpPingTelemetry.measurement
    tag_filter = '"node" =~ /^($node)$/ AND "site" =~ /^($site)$/'

    templating = [
        query_variable(
            name="site",
            label="Site",
            query=f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "site"',
            refresh=2,
        ),
        query_variable(
            name="node",
            label="Node",
            query=(f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "node" WHERE "site" =~ /^($site)$/'),
            refresh=2,
        ),
    ]

    nodes_seen_query = (
        f'SELECT count("v") FROM ('
        f'SELECT mean("percent_packet_loss") AS v FROM "{measurement}" '
        f'WHERE time > now() - 5m GROUP BY "node")'
    )
    nodes_up_query = (
        f'SELECT count("v") FROM ('
        f'SELECT mean("percent_packet_loss") AS v FROM "{measurement}" '
        f'WHERE time > now() - 5m GROUP BY "node") '
        f'WHERE "v" < 100'
    )
    avg_latency_query = f'SELECT mean("average_response_ms") FROM "{measurement}" WHERE $timeFilter AND {tag_filter}'
    avg_loss_query = f'SELECT mean("percent_packet_loss") FROM "{measurement}" WHERE $timeFilter AND {tag_filter}'
    latency_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f"WHERE $timeFilter AND {tag_filter} "
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    jitter_query = (
        f'SELECT mean("standard_deviation_ms") FROM "{measurement}" '
        f"WHERE $timeFilter AND {tag_filter} "
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    loss_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f"WHERE $timeFilter AND {tag_filter} "
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    latency_by_site_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f"WHERE $timeFilter AND {tag_filter} "
        f'GROUP BY time($__interval), "site" fill(null)'
    )
    loss_by_site_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f"WHERE $timeFilter AND {tag_filter} "
        f'GROUP BY time($__interval), "site" fill(null)'
    )
    top_latency_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" WHERE $timeFilter AND {tag_filter} GROUP BY "node"'
    )
    top_loss_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" WHERE $timeFilter AND {tag_filter} GROUP BY "node"'
    )

    panels = [
        # --- Row 1: scalar overview (y=0, h=4) ---
        stat_panel(
            panel_id=1,
            title="Nodes monitored",
            targets=[influxql_target(nodes_seen_query, result_format="table")],
            grid=grid_pos(0, 0, 6, 4),
        ),
        stat_panel(
            panel_id=2,
            title="Nodes responding",
            targets=[influxql_target(nodes_up_query, result_format="table")],
            grid=grid_pos(6, 0, 6, 4),
        ),
        stat_panel(
            panel_id=3,
            title="Avg latency (range)",
            targets=[influxql_target(avg_latency_query, result_format="table")],
            grid=grid_pos(12, 0, 6, 4),
            unit="ms",
            thresholds=LATENCY_THRESHOLDS,
        ),
        stat_panel(
            panel_id=4,
            title="Avg packet loss (range)",
            targets=[influxql_target(avg_loss_query, result_format="table")],
            grid=grid_pos(18, 0, 6, 4),
            unit="percent",
            thresholds=LOSS_THRESHOLDS,
        ),
        # --- Row 2: latency + jitter (y=4, h=8) ---
        timeseries_panel(
            panel_id=5,
            title="Ping latency (mean, ms)",
            targets=[influxql_target(latency_query, alias="$tag_node")],
            grid=grid_pos(0, 4, 12, 8),
            unit="ms",
            description="Mean ICMP round-trip time per node.",
        ),
        timeseries_panel(
            panel_id=6,
            title="Jitter (stddev, ms)",
            targets=[influxql_target(jitter_query, alias="$tag_node")],
            grid=grid_pos(12, 4, 12, 8),
            unit="ms",
            description="Standard deviation of ICMP RTT — flags unstable links.",
        ),
        # --- Row 3: loss timeseries (y=12, h=8) ---
        timeseries_panel(
            panel_id=7,
            title="Packet loss (%)",
            targets=[influxql_target(loss_query, alias="$tag_node")],
            grid=grid_pos(0, 12, 24, 8),
            unit="percent",
            description="Mean ICMP packet loss per node.",
        ),
        # --- Row 4: site rollups (y=20, h=8) ---
        timeseries_panel(
            panel_id=8,
            title="Latency by site (mean, ms)",
            targets=[influxql_target(latency_by_site_query, alias="$tag_site")],
            grid=grid_pos(0, 20, 12, 8),
            unit="ms",
            description="Mean RTT per site — useful for spotting site-wide degradation.",
        ),
        timeseries_panel(
            panel_id=9,
            title="Packet loss by site (%)",
            targets=[influxql_target(loss_by_site_query, alias="$tag_site")],
            grid=grid_pos(12, 20, 12, 8),
            unit="percent",
            description="Mean packet loss per site.",
        ),
        # --- Row 5: top-N worst offenders (y=28, h=10) ---
        bargauge_panel(
            panel_id=10,
            title="Top 10 — worst latency",
            targets=[influxql_target(top_latency_query, alias="$tag_node")],
            grid=grid_pos(0, 28, 12, 10),
            unit="ms",
            thresholds=LATENCY_THRESHOLDS,
            description="Nodes ranked by mean RTT over the dashboard time range.",
        ),
        bargauge_panel(
            panel_id=11,
            title="Top 10 — worst packet loss",
            targets=[influxql_target(top_loss_query, alias="$tag_node")],
            grid=grid_pos(12, 28, 12, 10),
            unit="percent",
            thresholds=LOSS_THRESHOLDS,
            description="Nodes ranked by mean packet loss over the dashboard time range.",
        ),
        # --- Row 6: reachability state timeline (y=38, h=12) ---
        state_timeline_panel(
            panel_id=12,
            title="Reachability (loss % per node)",
            targets=[influxql_target(loss_query, alias="$tag_node")],
            grid=grid_pos(0, 38, 24, 12),
            unit="percent",
            thresholds=LOSS_THRESHOLDS,
            description=(
                "Per-node loss heatmap over time. Green = clean, yellow/orange = degraded, red = mostly/fully down."
            ),
        ),
    ]

    return make_dashboard(
        uid="acex-icmp-overview",
        title="ACEX — ICMP Ping Overview",
        description=(
            f"Auto-generated from active node-instances in ACEX inventory. Currently tracking {len(pings)} node(s)."
        ),
        panels=panels,
        templating=templating,
    )


def snmp_overview_dashboard(registry: TelemetryRegistry) -> dict | None:
    """SNMP overview with site/node filters: which nodes answer, how long they were up, when they were not polled."""
    nodes: list[SnmpTelemetry] = registry.by_kind(SnmpTelemetry.kind)
    if not nodes:
        return None

    measurement = SnmpTelemetry.measurement
    tag_filter = '"node" =~ /^($node)$/ AND "site" =~ /^($site)$/'

    templating = [
        query_variable(
            name="site",
            label="Site",
            query=f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "site"',
            refresh=2,
        ),
        query_variable(
            name="node",
            label="Node",
            query=(f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "node" WHERE "site" =~ /^($site)$/'),
            refresh=2,
        ),
    ]

    def reporting_since(window: str) -> str:
        return (
            f'SELECT count("v") FROM ('
            f'SELECT last("uptime") AS v FROM "{measurement}" '
            f'WHERE time > now() - {window} AND {tag_filter} GROUP BY "node")'
        )

    # The newest uptime of each node in the range, in seconds; the extremes of those are the stats below.
    newest_uptime = (
        f'SELECT last("uptime") / {TICKS_PER_SECOND} AS v FROM "{measurement}" '
        f'WHERE $timeFilter AND {tag_filter} GROUP BY "node"'
    )
    shortest_query = f'SELECT min("v") FROM ({newest_uptime})'
    longest_query = f'SELECT max("v") FROM ({newest_uptime})'
    uptime_by_node_query = (
        f'SELECT last("uptime") / {TICKS_PER_SECOND} FROM "{measurement}" '
        f'WHERE $timeFilter AND {tag_filter} GROUP BY "node"'
    )
    uptime_query = (
        f'SELECT mean("uptime") / {TICKS_PER_DAY} FROM "{measurement}" '
        f'WHERE $timeFilter AND {tag_filter} GROUP BY time($__interval), "node" fill(null)'
    )
    polled_query = (
        f'SELECT count("uptime") FROM "{measurement}" '
        f'WHERE $timeFilter AND {tag_filter} GROUP BY time($__interval), "node" fill(0)'
    )

    panels = [
        # --- Row 1: scalar overview (y=0, h=4) ---
        stat_panel(
            panel_id=1,
            title="Nodes reporting (5 min)",
            targets=[influxql_target(reporting_since("5m"), result_format="table")],
            grid=grid_pos(0, 0, 6, 4),
            description="Nodes that sent an SNMP sample in the last five minutes.",
        ),
        stat_panel(
            panel_id=2,
            title="Nodes seen (24 h)",
            targets=[influxql_target(reporting_since("24h"), result_format="table")],
            grid=grid_pos(6, 0, 6, 4),
            description=(
                "Nodes that sent an SNMP sample in the last day. "
                "Fewer reporting than seen means some stopped answering."
            ),
        ),
        stat_panel(
            panel_id=3,
            title="Shortest uptime",
            targets=[influxql_target(shortest_query, result_format="table")],
            grid=grid_pos(12, 0, 6, 4),
            unit="dtdurations",
            thresholds=UPTIME_THRESHOLDS,
            description="The node that restarted most recently.",
        ),
        stat_panel(
            panel_id=4,
            title="Longest uptime",
            targets=[influxql_target(longest_query, result_format="table")],
            grid=grid_pos(18, 0, 6, 4),
            unit="dtdurations",
            thresholds=UPTIME_THRESHOLDS,
        ),
        # --- Row 2: uptime per node and over time (y=4, h=9) ---
        bargauge_panel(
            panel_id=5,
            title="Uptime by node",
            targets=[influxql_target(uptime_by_node_query, alias="$tag_node")],
            grid=grid_pos(0, 4, 12, 9),
            unit="dtdurations",
            thresholds=UPTIME_THRESHOLDS,
            limit=20,
            description=(
                "How long each node has been up. Red: under an hour, orange: under a day, yellow: under a week."
            ),
        ),
        timeseries_panel(
            panel_id=6,
            title="Uptime over time (days)",
            targets=[influxql_target(uptime_query, alias="$tag_node")],
            grid=grid_pos(12, 4, 12, 9),
            unit="short",
            description="Uptime of each node in days. A drop to zero is a restart.",
            span_nulls=True,
        ),
        # --- Row 3: polling state timeline (y=13, h=10) ---
        state_timeline_panel(
            panel_id=7,
            title="Polled over SNMP",
            targets=[influxql_target(polled_query, alias="$tag_node")],
            grid=grid_pos(0, 13, 24, 10),
            thresholds=POLLED_THRESHOLDS,
            min_interval="5m",
            description=(
                "Samples that arrived in each five-minute bucket per node. Green = the node answered, "
                "red = nothing arrived: the node did not answer, or the telemetry agent is not running."
            ),
        ),
    ]

    return make_dashboard(
        uid="acex-snmp-overview",
        title="ACEX — SNMP Overview",
        description=(
            f"Auto-generated from active node-instances in ACEX inventory. Currently tracking {len(nodes)} node(s)."
        ),
        panels=panels,
        templating=templating,
    )


# Map of dashboard UID -> (title, builder). The router uses this for both
# the index endpoint and the per-UID lookup. Keep keys stable — they are
# the deterministic Grafana UIDs.
DASHBOARDS = {
    "acex-icmp-overview": ("ACEX — ICMP Ping Overview", icmp_overview_dashboard),
    "acex-snmp-overview": ("ACEX — SNMP Overview", snmp_overview_dashboard),
}

# The capability whose data a dashboard shows. A dashboard is offered only when some telemetry agent is granted it: with
# no agent measuring that kind of telemetry every panel would say "No data". A dashboard that is not listed here is
# always offered.
DASHBOARD_CAPABILITIES = {
    "acex-icmp-overview": TelemetryCapability.icmp,
    "acex-snmp-overview": TelemetryCapability.snmp,
}
