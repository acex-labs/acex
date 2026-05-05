"""
Standard dashboard definitions, generated from the TelemetryRegistry.

Each function takes a TelemetryRegistry and returns a dashboard dict (or
None if there are no relevant components and the dashboard would be empty).
"""
from typing import Optional

from acex.observability.registry import TelemetryRegistry
from acex.observability.components.icmp_ping import IcmpPingTelemetry
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


def icmp_overview_dashboard(registry: TelemetryRegistry) -> Optional[dict]:
    """ICMP ping overview with site/node filters, rollups, top-N and reachability."""
    pings: list[IcmpPingTelemetry] = registry.by_kind(IcmpPingTelemetry.kind)
    if not pings:
        return None

    measurement = IcmpPingTelemetry.measurement
    node_filter = '"node" =~ /^($node)$/'

    templating = [
        query_variable(
            name="node",
            label="Node",
            query=f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "node"',
            refresh=2,
        ),
    ]

    nodes_seen_query = (
        f'SELECT count("v") FROM ('
        f'SELECT mean("average_response_ms") AS v FROM "{measurement}" '
        f'WHERE time > now() - 5m AND {node_filter} GROUP BY "node")'
    )
    nodes_up_query = (
        f'SELECT count("v") FROM ('
        f'SELECT mean("percent_packet_loss") AS v FROM "{measurement}" '
        f'WHERE time > now() - 5m AND {node_filter} GROUP BY "node") '
        f'WHERE "v" < 100'
    )
    avg_latency_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter}'
    )
    avg_loss_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter}'
    )
    latency_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} '
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    jitter_query = (
        f'SELECT mean("standard_deviation_ms") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} '
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    loss_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} '
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    latency_by_site_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} '
        f'GROUP BY time($__interval), "site" fill(null)'
    )
    loss_by_site_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} '
        f'GROUP BY time($__interval), "site" fill(null)'
    )
    top_latency_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} GROUP BY "node"'
    )
    top_loss_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f'WHERE $timeFilter AND {node_filter} GROUP BY "node"'
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
                "Per-node loss heatmap over time. "
                "Green = clean, yellow/orange = degraded, red = mostly/fully down."
            ),
        ),
    ]

    return make_dashboard(
        uid="acex-icmp-overview",
        title="ACEX — ICMP Ping Overview",
        description=(
            "Auto-generated from active node-instances in ACEX inventory. "
            f"Currently tracking {len(pings)} node(s)."
        ),
        panels=panels,
        templating=templating,
    )


# Map of dashboard UID -> (title, builder). The router uses this for both
# the index endpoint and the per-UID lookup. Keep keys stable — they are
# the deterministic Grafana UIDs.
DASHBOARDS = {
    "acex-icmp-overview": ("ACEX — ICMP Ping Overview", icmp_overview_dashboard),
}
