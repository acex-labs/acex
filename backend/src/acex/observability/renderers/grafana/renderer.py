from typing import Optional

from fastapi import HTTPException

from acex.observability.registry import TelemetryRegistry
from acex.observability.renderers.grafana.dashboards import DASHBOARDS
from acex.observability.renderers.grafana import datasources as ds_renderer
from acex.observability.settings import InfluxDBSettings


class GrafanaRenderer:
    """
    Serves generated Grafana dashboards and datasource definitions. v0 is
    read-only (manual import) — later this gets a `reconcile()` companion
    that pushes via Grafana API.
    """

    def __init__(
        self,
        registry: TelemetryRegistry,
        influxdb_settings: Optional[InfluxDBSettings] = None,
    ):
        self.registry = registry
        self.influxdb_settings = influxdb_settings

    def list_dashboards(self) -> list[dict]:
        return [
            {"uid": uid, "title": title}
            for uid, (title, _builder) in DASHBOARDS.items()
        ]

    def get_dashboard(self, uid: str) -> dict:
        entry = DASHBOARDS.get(uid)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Dashboard '{uid}' not found")
        _title, builder = entry
        dashboard = builder(self.registry)
        if dashboard is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Dashboard '{uid}' has no relevant telemetry components — "
                    "register matching nodes/components first."
                ),
            )
        return dashboard

    def list_datasources(self) -> list[dict]:
        if self.influxdb_settings is None:
            return []
        return ds_renderer.list_datasources(self.influxdb_settings)

    def get_datasource(self, uid: str) -> dict:
        if self.influxdb_settings is None:
            raise HTTPException(status_code=404, detail="No InfluxDB settings configured")
        result = ds_renderer.find_datasource(self.influxdb_settings, uid)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Datasource '{uid}' not found")
        return result
