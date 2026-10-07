"""Backend-default InfluxDB outputs applied to every TelemetryAgent's telegraf config."""

from acex.settings.base import Section
from acex_devkit.models.telemetry_agent import InfluxDBVersion
from pydantic import BaseModel

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


class InfluxDBSettings(Section, env_prefix="ACEX_INFLUXDB_"):
    """Backend-default InfluxDB outputs.

    The fields describe the primary output (ACEX_INFLUXDB_URL, _TOKEN, ...) and
    are unused until `url` is set. `extra_outputs` adds more, e.g. a replica;
    in the environment it is JSON in ACEX_INFLUXDB_EXTRA_OUTPUTS.

    Outputs are reported by group so a future release can target specific
    telemetry types (e.g. "syslog") with their own output. Only the reserved
    "default" group exists today.
    """

    url: str | None = None
    version: InfluxDBVersion = InfluxDBVersion.v3
    token: str | None = None
    organization: str | None = None
    bucket: str | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    content_encoding: str | None = None
    extra_outputs: list[InfluxDBOutput] = []

    @property
    def primary_output(self) -> InfluxDBOutput | None:
        if not self.url:
            return None
        return InfluxDBOutput(**self.model_dump(exclude={"extra_outputs"}))

    @property
    def default_outputs(self) -> list[InfluxDBOutput]:
        primary = self.primary_output
        return [primary, *self.extra_outputs] if primary else list(self.extra_outputs)

    @property
    def groups(self) -> dict[str, list[InfluxDBOutput]]:
        outputs = self.default_outputs
        return {DEFAULT_GROUP: outputs} if outputs else {}

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
