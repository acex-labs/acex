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


def influxql_target(query: str, ref_id: str = "A") -> dict:
    return {
        "refId": ref_id,
        "datasource": {"type": "influxdb", "uid": DEFAULT_DATASOURCE_UID},
        "query": query,
        "rawQuery": True,
        "resultFormat": "time_series",
    }


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
                    "steps": [{"color": "green", "value": None}],
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


def make_dashboard(
    uid: str,
    title: str,
    panels: list[dict],
    tags: Optional[list[str]] = None,
    description: Optional[str] = None,
    refresh: str = "30s",
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
        "templating": {"list": []},
        "annotations": {"list": []},
        "editable": False,
    }


def regex_alternation(values: list[str]) -> str:
    """Build a regex alternation safe for InfluxQL =~ /^(a|b|c)$/ patterns."""
    escaped = [v.replace("/", r"\/").replace("\\", r"\\") for v in values]
    return "|".join(escaped)
