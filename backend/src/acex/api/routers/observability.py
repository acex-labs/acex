from fastapi import APIRouter

from acex.constants import BASE_URL


def create_router(automation_engine):
    router = APIRouter(prefix=f"{BASE_URL}/observability")
    tags = ["Observability"]

    grafana = automation_engine.inventory.grafana_renderer

    router.add_api_route(
        "/grafana/dashboards",
        grafana.list_dashboards,
        methods=["GET"],
        tags=tags,
        summary="List available generated Grafana dashboards",
    )
    router.add_api_route(
        "/grafana/dashboards/{uid}",
        grafana.get_dashboard,
        methods=["GET"],
        tags=tags,
        summary="Get a generated Grafana dashboard JSON (manual import format)",
    )
    router.add_api_route(
        "/grafana/datasources",
        grafana.list_datasources,
        methods=["GET"],
        tags=tags,
        summary="List Grafana datasource definitions derived from backend-default InfluxDB outputs",
    )
    router.add_api_route(
        "/grafana/datasources/{uid}",
        grafana.get_datasource,
        methods=["GET"],
        tags=tags,
        summary="Get a Grafana datasource creation body (POST to /api/datasources)",
    )

    return router
