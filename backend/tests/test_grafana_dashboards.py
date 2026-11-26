"""The generated Grafana dashboards: the SNMP overview, and what the SNMP input writes that it reads."""

import json
import re
from types import SimpleNamespace

import pytest
from acex.observability.capability import TelemetryCapability
from acex.observability.components.icmp_ping import IcmpPingTelemetry
from acex.observability.components.snmp import SnmpTelemetry
from acex.observability.renderers.grafana.dashboards import DASHBOARD_CAPABILITIES, DASHBOARDS, snmp_overview_dashboard
from acex.observability.renderers.grafana.renderer import GrafanaRenderer
from acex.observability.renderers.telegraf import render_inputs
from fastapi import HTTPException

UID = "acex-snmp-overview"


def registry(*components, granted=(TelemetryCapability.snmp, TelemetryCapability.icmp)):
    """What the dashboards ask of the registry: the components of a kind, and the capabilities some agent is granted."""
    return SimpleNamespace(
        by_kind=lambda kind: [c for c in components if c.kind == kind],
        granted_capabilities=lambda: set(granted),
    )


def snmp_node(node_id=1, hostname="got-sw-1", site="got", region="EMEA"):
    return SnmpTelemetry(node_id=node_id, hostname=hostname, target_ip="192.0.2.1", site=site, region=region)


def queries(dashboard) -> list[str]:
    found = [t["query"] for panel in dashboard["panels"] for t in panel["targets"]]
    found += [v["query"] for v in dashboard["templating"]["list"]]
    return found


def should_have_no_dashboard_without_snmp_nodes():
    assert snmp_overview_dashboard(registry()) is None
    ping_only = registry(IcmpPingTelemetry(node_id=1, hostname="r1", target_ip="192.0.2.9"))
    assert snmp_overview_dashboard(ping_only) is None


def should_be_listed_under_a_stable_uid():
    assert DASHBOARDS[UID][0] == "ACEX — SNMP Overview"
    listed = GrafanaRenderer(registry(snmp_node())).list_dashboards()
    assert {"uid": UID, "title": "ACEX — SNMP Overview"} in listed


def should_be_served_for_snmp_nodes_and_refused_without(monkeypatch):
    dashboard = GrafanaRenderer(registry(snmp_node())).get_dashboard(UID)
    assert dashboard["uid"] == UID
    assert "1 node(s)" in dashboard["description"]
    with pytest.raises(HTTPException) as refused:
        GrafanaRenderer(registry()).get_dashboard(UID)
    assert refused.value.status_code == 404


def should_offer_only_the_dashboards_of_a_kind_some_agent_measures():
    uids = lambda granted: {d["uid"] for d in GrafanaRenderer(registry(granted=granted)).list_dashboards()}  # noqa: E731

    assert uids(()) == set()
    assert uids({TelemetryCapability.snmp}) == {"acex-snmp-overview"}
    assert uids({TelemetryCapability.icmp}) == {"acex-icmp-overview"}
    assert uids({TelemetryCapability.snmp, TelemetryCapability.icmp}) == set(DASHBOARDS)
    # A capability that no dashboard shows offers nothing.
    assert uids({TelemetryCapability.syslog_rfc5424}) == set()


def should_refuse_a_dashboard_no_agent_measures_even_with_nodes_to_measure():
    nodes = registry(
        snmp_node(),
        IcmpPingTelemetry(node_id=2, hostname="r1", target_ip="192.0.2.9"),
        granted={TelemetryCapability.snmp},
    )
    renderer = GrafanaRenderer(nodes)

    assert renderer.get_dashboard("acex-snmp-overview")["uid"] == "acex-snmp-overview"
    with pytest.raises(HTTPException) as refused:
        renderer.get_dashboard("acex-icmp-overview")
    assert refused.value.status_code == 404
    assert "icmp" in refused.value.detail and "no telemetry agent" in refused.value.detail


def should_always_offer_a_dashboard_that_names_no_capability(monkeypatch):
    monkeypatch.setitem(DASHBOARDS, "custom", ("Custom", lambda registry: {"uid": "custom", "panels": []}))
    assert "custom" not in DASHBOARD_CAPABILITIES

    renderer = GrafanaRenderer(registry(granted=()))

    assert {"uid": "custom", "title": "Custom"} in renderer.list_dashboards()
    assert renderer.get_dashboard("custom")["uid"] == "custom"


def should_query_only_the_measurement_the_snmp_input_writes():
    dashboard = snmp_overview_dashboard(registry(snmp_node(), snmp_node(2, "sto-sw-1", "sto")))
    measurements = {m for q in queries(dashboard) for m in re.findall(r'FROM "([^"]+)"', q)}
    assert measurements == {SnmpTelemetry.measurement}
    assert not any("ping" in q for q in queries(dashboard))


def should_write_the_measurement_the_dashboard_reads_with_the_node_as_a_tag():
    node = snmp_node()
    config = node.telegraf_input()["config"]
    assert config["name"] == SnmpTelemetry.measurement == "snmp"
    assert node.hostname not in config["name"]
    assert node.telegraf_input()["tags"]["node"] == node.hostname
    assert node.telegraf_input()["tags"]["site"] == "got"
    rendered = render_inputs([node])
    assert 'name = "snmp"' in rendered
    assert 'name = "got-sw-1"' not in rendered


def should_filter_on_the_tags_the_input_writes():
    dashboard = snmp_overview_dashboard(registry(snmp_node()))
    tags = set(snmp_node().tags())
    assert {"node", "site"} <= tags
    names = {v["name"] for v in dashboard["templating"]["list"]}
    assert names == {"site", "node"}
    filtered = [q for q in queries(dashboard) if '"node" =~ /^($node)$/' in q]
    assert len(filtered) >= 6
    assert all('"site" =~ /^($site)$/' in q for q in filtered)


def should_read_uptime_as_hundredths_of_a_second():
    dashboard = snmp_overview_dashboard(registry(snmp_node()))
    by_title = {p["title"]: p for p in dashboard["panels"]}
    in_seconds = by_title["Uptime by node"]["targets"][0]["query"]
    assert 'last("uptime") / 100' in in_seconds
    assert by_title["Uptime by node"]["fieldConfig"]["defaults"]["unit"] == "dtdurations"
    in_days = by_title["Uptime over time (days)"]["targets"][0]["query"]
    assert '"uptime") / 8640000' in in_days
    assert by_title["Uptime over time (days)"]["fieldConfig"]["defaults"]["custom"]["spanNulls"] is True


def should_count_samples_in_buckets_wider_than_the_polling_interval():
    dashboard = snmp_overview_dashboard(registry(snmp_node()))
    polled = next(p for p in dashboard["panels"] if p["title"] == "Polled over SNMP")
    assert polled["type"] == "state-timeline"
    assert polled["interval"] == "5m"
    assert "fill(0)" in polled["targets"][0]["query"]
    steps = polled["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert [s["color"] for s in steps] == ["red", "green"] and steps[1]["value"] == 1


def should_lay_out_panels_without_overlap_inside_24_columns():
    panels = snmp_overview_dashboard(registry(snmp_node()))["panels"]
    ids = [p["id"] for p in panels]
    assert len(ids) == len(set(ids))
    taken = set()
    for p in panels:
        g = p["gridPos"]
        assert g["x"] >= 0 and g["x"] + g["w"] <= 24
        cells = {(x, y) for x in range(g["x"], g["x"] + g["w"]) for y in range(g["y"], g["y"] + g["h"])}
        assert not cells & taken, p["title"]
        taken |= cells


def should_be_plain_json_that_grafana_can_import():
    dashboard = snmp_overview_dashboard(registry(snmp_node()))
    assert json.loads(json.dumps(dashboard)) == dashboard
    assert dashboard["editable"] is False and dashboard["templating"]["list"]
    sources = {p["datasource"]["uid"] for p in dashboard["panels"]}
    assert sources == {"acex-influxdb-0"}


def should_show_a_bar_for_every_node_in_the_ranked_panels():
    """The panels rank nodes in a table with a row for each; a bar gauge that does not show each value reduces the
    table to its last row and draws one bar."""
    from acex.observability.renderers.grafana.dashboards import icmp_overview_dashboard

    snmp = snmp_overview_dashboard(registry(snmp_node()))
    icmp = icmp_overview_dashboard(registry(IcmpPingTelemetry(node_id=1, hostname="r1", target_ip="192.0.2.9")))
    ranked = [p for d in (snmp, icmp) for p in d["panels"] if p["type"] == "bargauge"]
    assert len(ranked) == 3
    assert all(p["options"]["reduceOptions"]["values"] is True for p in ranked)
