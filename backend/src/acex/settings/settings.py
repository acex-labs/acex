"""The root `Settings`: every section, dev mode, and the production safety check."""

from acex.settings.ai_ops import AIOpsSettings
from acex.settings.bug_report import BugReportSettings
from acex.settings.influxdb import InfluxDBSettings
from acex.settings.section import Section
from acex.settings.sections import (
    CorsSettings,
    CredentialSettings,
    DatabaseSettings,
    OidcSettings,
    RabbitMQSettings,
    ServerSettings,
)
from pydantic import Field, model_validator


class UnsafeConfiguration(RuntimeError):
    """Raised when a production start would expose the API."""


class Settings(Section):
    #: Development mode (ACEX_DEV, or `acex-api --dev`). It relaxes the checks in
    #: `check()` — the API may then run unauthenticated and answer any origin —
    #: so it must never be turned on for a deployment reachable by anyone else.
    dev: bool = False

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    oidc: OidcSettings = Field(default_factory=OidcSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
    credentials: CredentialSettings = Field(default_factory=CredentialSettings)
    influxdb: InfluxDBSettings = Field(default_factory=InfluxDBSettings)
    ai_ops: AIOpsSettings = Field(default_factory=AIOpsSettings)
    bug_report: BugReportSettings = Field(default_factory=BugReportSettings)
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)

    @model_validator(mode="after")
    def _dev_conveniences(self) -> "Settings":
        # Conveniences, not overrides: a value set in code or env still wins.
        if self.dev:
            if "allowed_origins" not in self.cors.model_fields_set:
                self.cors.allowed_origins = ["*"]
            if "reload" not in self.server.model_fields_set:
                self.server.reload = True
        return self

    @property
    def authenticated(self) -> bool:
        return self.oidc.issuer_url is not None

    def check(self) -> None:
        """Refuse configurations that would expose the API. Called before an app is built."""
        if self.dev:
            return

        problems = []
        if not self.authenticated:
            problems.append(
                "ACEX_OIDC_ISSUER_URL is not set, which leaves every endpoint open to "
                "unauthenticated callers. Set it, or enable dev mode (--dev, ACEX_DEV=1 "
                "or Settings(dev=True)) to run without auth."
            )
        if "*" in self.cors.allowed_origins:
            problems.append(
                'ACEX_CORS_ALLOWED_ORIGINS contains "*". The API sends credentials, so a '
                "wildcard lets any site on the web make authenticated calls on a user's "
                "behalf. Name the origins that need access, or enable dev mode."
            )
        if problems:
            raise UnsafeConfiguration("Refusing to start:\n  - " + "\n  - ".join(problems))
