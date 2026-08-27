import os

from acex_devkit.models.telemetry_agent import InfluxDBVersion
from pydantic import BaseModel

ENV_PREFIX = "ACEX_INFLUXDB_"
DEFAULT_GROUP = "default"


class InfluxDBOutput(BaseModel):
    """A single InfluxDB output target."""

    version: InfluxDBVersion = InfluxDBVersion.v3
    url: str = "http://localhost:8086"
    # v2 / v3
    token: str | None = None
    organization: str | None = None
    bucket: str | None = None  # v2 only
    # v1 / v3 (v3 went back to "database" terminology)
    database: str | None = None
    username: str | None = None  # v1 only
    password: str | None = None  # v1 only
    # transport (all versions)
    content_encoding: str | None = None


class InfluxDBSettings(BaseModel):
    """
    Backend-level InfluxDB outputs applied to every TelemetryAgent's telegraf config.

    Outputs are keyed by group name so a future release can target specific
    telemetry types (e.g. "syslog", "telemetry") with their own output,
    falling back to the reserved "default" group for anything without an
    override. Only the "default" group is read anywhere today — group
    overrides are not yet resolved by the renderer.

    Configured via env vars (ACEX_INFLUXDB_*) for the default group, or via
    `AutomationEngine.set_influxdb(...)` / `add_influxdb(...)`.
    """

    groups: dict[str, list[InfluxDBOutput]] = {}

    @classmethod
    def from_env(cls) -> "InfluxDBSettings":
        """Default group from ACEX_INFLUXDB_* env vars, or empty if URL unset."""
        url = os.environ.get(f"{ENV_PREFIX}URL")
        if not url:
            return cls(groups={})

        kwargs: dict = {"url": url}
        version = os.environ.get(f"{ENV_PREFIX}VERSION")
        if version:
            kwargs["version"] = InfluxDBVersion(version)
        for field in (
            "token",
            "organization",
            "bucket",
            "database",
            "username",
            "password",
            "content_encoding",
        ):
            value = os.environ.get(f"{ENV_PREFIX}{field.upper()}")
            if value is not None:
                kwargs[field] = value
        return cls(groups={DEFAULT_GROUP: [InfluxDBOutput(**kwargs)]})

    @property
    def default_outputs(self) -> list[InfluxDBOutput]:
        return self.groups.get(DEFAULT_GROUP, [])

    def is_configured(self) -> bool:
        return bool(self.default_outputs)

    def redacted(self) -> dict[str, list[dict]]:
        """Configured groups/outputs with secrets replaced by a boolean flag."""
        return {
            group: [
                {
                    **output.model_dump(exclude={"token", "password"}),
                    "token_set": bool(output.token),
                    "password_set": bool(output.password),
                }
                for output in outputs
            ]
            for group, outputs in self.groups.items()
        }
