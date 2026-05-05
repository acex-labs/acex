"""
Thin builders for Grafana dashboard JSON.

Panels reference a deterministic datasource UID (`acex-influxdb-0`,
matching the first backend-default InfluxDB output) so dashboards work
under sidecar/configmap provisioning and direct API push — neither
processes the `__inputs` placeholder pattern that Grafana's Import UI
uses. Users must ensure the matching datasource exists in Grafana
(generate it via /observability/grafana/datasources/{uid}).
"""
from typing import Optional

from acex.observability.renderers.grafana.datasources import datasource_uid

DEFAULT_DATASOURCE_UID = datasource_uid(0)


def grid_pos(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def influxql_target(
    query: str,
    ref_id: str = "A",
    alias: str = "",
    result_format: str = "time_series",
) -> dict:
    target = {
        "refId": ref_id,
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "query": query,
        "rawQuery": True,
        "resultFormat": result_format,
    }
    if alias:
        target["alias"] = alias
    return target


def timeseries_panel(
    panel_id: int,
    title: str,
    targets: list[dict],
    grid: dict,
    unit: str = "short",
    description: Optional[str] = None,
) -> dict:
    panel = {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "gridPos": grid,
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "linear",
                    "fillOpacity": 10,
                    "showPoints": "never",
                },
            },
            "overrides": [],
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }
    if description:
        panel["description"] = description
    return panel


def stat_panel(
    panel_id: int,
    title: str,
    targets: list[dict],
    grid: dict,
    unit: str = "short",
    color_mode: str = "value",
    thresholds: Optional[list[dict]] = None,
) -> dict:
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "gridPos": grid,
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": thresholds or [{"color": "green", "value": None}],
                },
            },
            "overrides": [],
        },
        "options": {
            "colorMode": color_mode,
            "graphMode": "area",
            "justifyMode": "auto",
            "textMode": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
    }


def bargauge_panel(
    panel_id: int,
    title: str,
    targets: list[dict],
    grid: dict,
    unit: str = "short",
    thresholds: Optional[list[dict]] = None,
    limit: int = 10,
    description: Optional[str] = None,
) -> dict:
    panel = {
        "id": panel_id,
        "type": "bargauge",
        "title": title,
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "gridPos": grid,
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "thresholds"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": thresholds or [{"color": "green", "value": None}],
                },
            },
            "overrides": [],
        },
        "options": {
            "displayMode": "gradient",
            "orientation": "horizontal",
            "showUnfilled": True,
            "valueMode": "color",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        },
        "transformations": [
            {"id": "reduce", "options": {"reducers": ["mean"]}},
            {"id": "sortBy", "options": {"sort": [{"field": "Mean", "desc": True}]}},
            {"id": "limit", "options": {"limitField": limit}},
        ],
    }
    if description:
        panel["description"] = description
    return panel


def state_timeline_panel(
    panel_id: int,
    title: str,
    targets: list[dict],
    grid: dict,
    unit: str = "short",
    thresholds: Optional[list[dict]] = None,
    description: Optional[str] = None,
) -> dict:
    panel = {
        "id": panel_id,
        "type": "state-timeline",
        "title": title,
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "gridPos": grid,
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "thresholds"},
                "custom": {"fillOpacity": 80, "lineWidth": 0},
                "thresholds": {
                    "mode": "absolute",
                    "steps": thresholds or [{"color": "green", "value": None}],
                },
            },
            "overrides": [],
        },
        "options": {
            "mergeValues": False,
            "showValue": "never",
            "alignValue": "left",
            "rowHeight": 0.9,
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": False},
            "tooltip": {"mode": "single", "sort": "none"},
        },
    }
    if description:
        panel["description"] = description
    return panel


def query_variable(
    name: str,
    query: str,
    label: Optional[str] = None,
    multi: bool = True,
    include_all: bool = True,
    refresh: int = 1,
) -> dict:
    """InfluxQL-backed Grafana template variable.

    refresh: 1 = on dashboard load, 2 = on time-range change.
    """
    var = {
        "name": name,
        "type": "query",
        "label": label or name.title(),
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "query": query,
        "refresh": refresh,
        "multi": multi,
        "includeAll": include_all,
        "options": [],
        "regex": "",
        "sort": 1,
    }
    if include_all:
        var["current"] = {"selected": True, "text": "All", "value": "$__all"}
    return var


def make_dashboard(
    uid: str,
    title: str,
    panels: list[dict],
    tags: Optional[list[str]] = None,
    description: Optional[str] = None,
    refresh: str = "30s",
    templating: Optional[list[dict]] = None,
) -> dict:
    return {
        "uid": uid,
        "title": title,
        "description": description or "",
        "tags": tags or ["acex"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": refresh,
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "panels": panels,
        "templating": {"list": templating or []},
        "annotations": {"list": []},
        "editable": False,
    }


def regex_alternation(values: list[str]) -> str:
    """Build a regex alternation safe for InfluxQL =~ /^(a|b|c)$/ patterns."""
    escaped = [v.replace("/", r"\/").replace("\\", r"\\") for v in values]
    return "|".join(escaped)
