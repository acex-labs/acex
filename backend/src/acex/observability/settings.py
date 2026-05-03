import os
from typing import List, Optional

from pydantic import BaseModel

from acex.observability.agents.models import InfluxDBVersion


ENV_PREFIX = "ACEX_INFLUXDB_"


class InfluxDBOutput(BaseModel):
    """
    A single InfluxDB output target.

    Same shape as `OutputDestination` (the per-agent DB row) so the
    telegraf renderer can treat both polymorphically.
    """

    version: InfluxDBVersion = InfluxDBVersion.v2
    url: str = "http://localhost:8086"
    # v2 / v3
    token: Optional[str] = None
    organization: Optional[str] = None
    bucket: Optional[str] = None  # v2 only
    # v1 / v3 (v3 went back to "database" terminology)
    database: Optional[str] = None
    username: Optional[str] = None  # v1 only
    password: Optional[str] = None  # v1 only
    # transport (all versions)
    content_encoding: Optional[str] = None


class InfluxDBSettings(BaseModel):
    """
    Backend-level default InfluxDB outputs applied to every TelemetryAgent.

    Agents can add their own additional `OutputDestination` rows on top —
    the renderer concatenates defaults + agent-specific into the telegraf
    config. This means a global setting like a primary + replica InfluxDB
    is configured once in app.py and inherited by all agents.

    Configured via env vars (ACEX_INFLUXDB_*) for a single output, or via
    `AutomationEngine.set_influxdb(...)` / `add_influxdb(...)`.
    """

    outputs: List[InfluxDBOutput] = []

    @classmethod
    def from_env(cls) -> "InfluxDBSettings":
        """One output from ACEX_INFLUXDB_* env vars, or empty if URL unset."""
        url = os.environ.get(f"{ENV_PREFIX}URL")
        if not url:
            return cls(outputs=[])

        kwargs: dict = {"url": url}
        version = os.environ.get(f"{ENV_PREFIX}VERSION")
        if version:
            kwargs["version"] = InfluxDBVersion(version)
        for field in (
            "token", "organization", "bucket",
            "database", "username", "password", "content_encoding",
        ):
            value = os.environ.get(f"{ENV_PREFIX}{field.upper()}")
            if value is not None:
                kwargs[field] = value
        return cls(outputs=[InfluxDBOutput(**kwargs)])

    def is_configured(self) -> bool:
        return bool(self.outputs)
