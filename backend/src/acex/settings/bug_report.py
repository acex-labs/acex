"""Where bug reports submitted from the web UI are sent. Each target is off until configured."""

from acex.settings.section import Section
from pydantic import Field, SecretStr


class AdoBugReportSettings(Section, name="bug_report.ado"):
    """Azure DevOps: each report becomes a User Story under a feature."""

    service_pat: SecretStr | None = None
    org: str | None = None
    project: str | None = None
    #: Work item id of the feature the User Stories are created under.
    feature_id: int | None = None

    @property
    def configured(self) -> bool:
        return bool(self.service_pat and self.org and self.project and self.feature_id)


class SlackBugReportSettings(Section, name="bug_report.slack"):
    """Slack: each report is posted to an incoming webhook."""

    #: The URL carries its own credential, so it is kept secret.
    webhook_url: SecretStr | None = None

    @property
    def configured(self) -> bool:
        return self.webhook_url is not None


class FileBugReportSettings(Section, name="bug_report.file"):
    """Local files: each report is written as JSON, screenshots alongside."""

    dir: str | None = None

    @property
    def configured(self) -> bool:
        return self.dir is not None


class BugReportSettings(Section, name="bug_report"):
    ado: AdoBugReportSettings = Field(default_factory=AdoBugReportSettings)
    slack: SlackBugReportSettings = Field(default_factory=SlackBugReportSettings)
    file: FileBugReportSettings = Field(default_factory=FileBugReportSettings)
