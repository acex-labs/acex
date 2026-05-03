"""
Standard dashboard definitions, generated from the TelemetryRegistry.

Each function takes a TelemetryRegistry and returns a dashboard dict (or
None if there are no relevant components and the dashboard would be empty).
"""
from typing import Optional

from acex.observability.registry import TelemetryRegistry
from acex.observability.components.icmp_ping import IcmpPingTelemetry
from acex.observability.renderers.grafana.builder import (
    grid_pos,
    influxql_target,
    make_dashboard,
    regex_alternation,
    stat_panel,
    timeseries_panel,
)


def icmp_overview_dashboard(registry: TelemetryRegistry) -> Optional[dict]:
    """ICMP ping overview — one row per node-instance with active monitoring."""
    pings: list[IcmpPingTelemetry] = registry.by_kind(IcmpPingTelemetry.kind)
    if not pings:
        return None

    hostnames = sorted({p.hostname for p in pings})
    host_regex = regex_alternation(hostnames)
    measurement = IcmpPingTelemetry.measurement

    latency_query = (
        f'SELECT mean("average_response_ms") FROM "{measurement}" '
        f'WHERE $timeFilter AND "node" =~ /^({host_regex})$/ '
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    loss_query = (
        f'SELECT mean("percent_packet_loss") FROM "{measurement}" '
        f'WHERE $timeFilter AND "node" =~ /^({host_regex})$/ '
        f'GROUP BY time($__interval), "node" fill(null)'
    )
    nodes_up_query = (
        f'SELECT count(distinct("node")) FROM "{measurement}" '
        f'WHERE time > now() - 5m AND "percent_packet_loss" < 100 '
        f'AND "node" =~ /^({host_regex})$/'
    )

    panels = [
        stat_panel(
            panel_id=1,
            title="Nodes monitored",
            targets=[influxql_target(
                f'SELECT count(distinct("node")) FROM "{measurement}" '
                f'WHERE time > now() - 5m AND "node" =~ /^({host_regex})$/'
            )],
            grid=grid_pos(0, 0, 6, 4),
        ),
        stat_panel(
            panel_id=2,
            title="Nodes responding",
            targets=[influxql_target(nodes_up_query)],
            grid=grid_pos(6, 0, 6, 4),
            color_mode="value",
        ),
        timeseries_panel(
            panel_id=3,
            title="Ping latency (mean, ms)",
            targets=[influxql_target(latency_query)],
            grid=grid_pos(0, 4, 24, 8),
            unit="ms",
            description="Mean ICMP round-trip time per active node-instance.",
        ),
        timeseries_panel(
            panel_id=4,
            title="Packet loss (%)",
            targets=[influxql_target(loss_query)],
            grid=grid_pos(0, 12, 24, 8),
            unit="percent",
            description="Mean ICMP packet loss per active node-instance.",
        ),
    ]

    return make_dashboard(
        uid="acex-icmp-overview",
        title="ACEX — ICMP Ping Overview",
        description=(
            "Auto-generated from active node-instances in ACEX inventory. "
            f"Currently tracking {len(hostnames)} node(s)."
        ),
        panels=panels,
    )


# Map of dashboard UID -> (title, builder). The router uses this for both
# the index endpoint and the per-UID lookup. Keep keys stable — they are
# the deterministic Grafana UIDs.
DASHBOARDS = {
    "acex-icmp-overview": ("ACEX — ICMP Ping Overview", icmp_overview_dashboard),
}
