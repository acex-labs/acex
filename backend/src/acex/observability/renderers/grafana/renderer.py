from acex.observability.registry import TelemetryRegistry
from acex.observability.renderers.grafana import datasources as ds_renderer
from acex.observability.renderers.grafana.dashboards import DASHBOARD_CAPABILITIES, DASHBOARDS
from acex.observability.settings import InfluxDBSettings
from fastapi import HTTPException


class GrafanaRenderer:
    """
    Serves generated Grafana dashboards and datasource definitions. v0 is
    read-only (manual import) — later this gets a `reconcile()` companion
    that pushes via Grafana API.
    """

    def __init__(
        self,
        registry: TelemetryRegistry,
        influxdb_settings: InfluxDBSettings | None = None,
    ):
        self.registry = registry
        self.influxdb_settings = influxdb_settings

    def _offered(self, uid: str, granted: set) -> bool:
        needs = DASHBOARD_CAPABILITIES.get(uid)
        return needs is None or needs in granted

    def list_dashboards(self) -> list[dict]:
        """The dashboards worth having: those of a kind some telemetry agent measures. A dashboard that is not
        listed is not synced into Grafana, and is removed from it if it was."""
        granted = self.registry.granted_capabilities()
        return [
            {"uid": uid, "title": title} for uid, (title, _builder) in DASHBOARDS.items() if self._offered(uid, granted)
        ]

    def get_dashboard(self, uid: str) -> dict:
        entry = DASHBOARDS.get(uid)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Dashboard '{uid}' not found")
        if not self._offered(uid, self.registry.granted_capabilities()):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Dashboard '{uid}' shows {DASHBOARD_CAPABILITIES[uid]} telemetry, and no telemetry agent "
                    f"is granted the {DASHBOARD_CAPABILITIES[uid]} capability."
                ),
            )
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
