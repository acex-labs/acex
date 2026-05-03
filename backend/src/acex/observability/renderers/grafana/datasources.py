"""
Grafana datasource definitions generated from backend-default
InfluxDB outputs (configured via `set_influxdb` / `add_influxdb`).

Returned shape matches Grafana's `POST /api/datasources` body, so the
user can curl the endpoint output directly to Grafana to create the
matching datasource:

    curl http://acex/api/v1/observability/grafana/datasources/acex-influxdb-0 \\
      | curl -X POST http://grafana/api/datasources \\
        -H 'Authorization: Bearer ...' -H 'Content-Type: application/json' \\
        --data @-

UIDs are deterministic (`acex-influxdb-{index}`) so re-runs are
idempotent — same UID, same datasource, no duplicates.
"""
from typing import Optional

from acex.observability.agents.models import InfluxDBVersion
from acex.observability.settings import InfluxDBOutput, InfluxDBSettings


def _slugify_url(url: str) -> str:
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace(":", "-")
        .replace("/", "-")
        .rstrip("-")
    )


def datasource_uid(index: int) -> str:
    return f"acex-influxdb-{index}"


def make_datasource(output: InfluxDBOutput, index: int) -> dict:
    """Build a Grafana datasource creation body from one InfluxDBOutput."""
    ds: dict = {
        "uid": datasource_uid(index),
        "name": f"ACEX InfluxDB ({_slugify_url(output.url)})",
        "type": "influxdb",
        "url": output.url,
        "access": "proxy",
        "isDefault": index == 0,
        "editable": False,
        "jsonData": {},
        "secureJsonData": {},
    }

    if output.version == InfluxDBVersion.v3:
        # v3 InfluxQL via the v2-compatible HTTP API. Token is sent as a
        # bearer header — InfluxDB v3 doesn't use the v2 token field of
        # the Grafana plugin. May need manual tweaking depending on plugin
        # version and v3 deployment specifics.
        ds["jsonData"]["version"] = "InfluxQL"
        ds["jsonData"]["dbName"] = output.database or ""
        ds["jsonData"]["httpMode"] = "POST"
        if output.token:
            ds["jsonData"]["httpHeaderName1"] = "Authorization"
            ds["secureJsonData"]["httpHeaderValue1"] = f"Bearer {output.token}"
    elif output.version == InfluxDBVersion.v2:
        ds["jsonData"]["version"] = "Flux"
        ds["jsonData"]["organization"] = output.organization or ""
        ds["jsonData"]["defaultBucket"] = output.bucket or ""
        if output.token:
            ds["secureJsonData"]["token"] = output.token
    else:  # v1
        ds["jsonData"]["dbName"] = output.database or ""
        if output.username:
            ds["user"] = output.username
        if output.password:
            ds["secureJsonData"]["password"] = output.password

    return ds


def list_datasources(settings: InfluxDBSettings) -> list[dict]:
    """List datasources (uid + name + url) for the index endpoint."""
    return [
        {
            "uid": datasource_uid(i),
            "name": f"ACEX InfluxDB ({_slugify_url(o.url)})",
            "url": o.url,
            "version": o.version.value,
        }
        for i, o in enumerate(settings.outputs)
    ]


def find_datasource(settings: InfluxDBSettings, uid: str) -> Optional[dict]:
    """Return the full datasource definition for a given UID, or None."""
    for i, o in enumerate(settings.outputs):
        if datasource_uid(i) == uid:
            return make_datasource(o, i)
    return None
