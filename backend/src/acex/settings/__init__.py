"""Runtime settings for the AutomationEngine.

Every plain value the engine is configured with is declared here, once, and
can then be given either in code or from the environment. Anything that is
code rather than a value (integration plugins, datasource plugins, ConfigMap
directories) stays a method on AutomationEngine, since only an integrator's
app.py can express it.

    ae = AutomationEngine()                               # all from the environment
    ae = AutomationEngine(settings=Settings(dev=True))    # code wins, env fills the rest

Adding a setting: add a field to the section it belongs to (sections.py, or
its own module). Its environment variable is ACEX_<SECTION>_<FIELD>, which
spells out where it lives under `Settings`; see `Section`.

Adding a section: subclass `Section` with a `name` and add it as a field of
`Settings` in settings.py under that same name.

The engine refuses to build an app on a configuration that would quietly
expose it; see `Settings.check`. Development conveniences live behind
`Settings.dev`.
"""

from acex.settings.ai_ops import AIChainLevel, AIModelMeta, AIOpsSettings, AIProvider
from acex.settings.bug_report import (
    AdoBugReportSettings,
    BugReportSettings,
    FileBugReportSettings,
    SlackBugReportSettings,
)
from acex.settings.influxdb import InfluxDBOutput, InfluxDBSettings
from acex.settings.section import Section
from acex.settings.sections import (
    CorsSettings,
    CredentialSettings,
    DatabaseSettings,
    OidcSettings,
    RabbitMQSettings,
    ServerSettings,
    VaultSettings,
)
from acex.settings.settings import Settings, UnsafeConfiguration

__all__ = [
    "AIChainLevel",
    "AIModelMeta",
    "AIOpsSettings",
    "AIProvider",
    "AdoBugReportSettings",
    "BugReportSettings",
    "CorsSettings",
    "CredentialSettings",
    "DatabaseSettings",
    "FileBugReportSettings",
    "InfluxDBOutput",
    "InfluxDBSettings",
    "OidcSettings",
    "RabbitMQSettings",
    "Section",
    "ServerSettings",
    "Settings",
    "SlackBugReportSettings",
    "UnsafeConfiguration",
    "VaultSettings",
]
