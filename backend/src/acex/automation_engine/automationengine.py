import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from acex.database import Connection
    from acex.plugins.integrations import IntegrationPluginBase, IntegrationPluginFactoryBase
    from acex.settings import Settings
    from fastapi import FastAPI


def _deprecated(old: str, new: str) -> None:
    warnings.warn(f"{old} is deprecated; {new}.", DeprecationWarning, stacklevel=3)


class AutomationEngine:
    def __init__(
        self,
        db_connection: "Connection|None" = None,
        assets_plugin: "IntegrationPluginBase|None" = None,
        logical_nodes_plugin: "IntegrationPluginBase|None" = None,
        sites_plugin: "IntegrationPluginBase|None" = None,
        contacts_plugin: "IntegrationPluginBase|None" = None,
        dev_mode: bool | None = None,
        settings: "Settings|None" = None,
    ):
        """Build the engine.

        `settings` holds every plain value the engine runs with (see
        acex.settings). Left out, it is read from the environment. Plugins
        are code rather than values, so they are passed here or registered
        with add_integration().

        `db_connection` overrides `settings.db` with a ready-made Connection.
        `dev_mode` is deprecated in favour of `Settings(dev=True)`.
        """
        # Lazy imports - only load when AutomationEngine is instantiated
        from acex.api.api import Api
        from acex.automation_engine.integrations import Integrations
        from acex.compilers import ConfigCompiler
        from acex.database import Connection, DatabaseManager
        from acex.device_configs import DeviceConfigManager
        from acex.inventory import Inventory
        from acex.jobs import JobManager
        from acex.management_connections import ManagementConnectionManager
        from acex.messaging import JobProducer
        from acex.plugins import PluginManager
        from acex.settings import Settings

        if dev_mode is not None:
            _deprecated("AutomationEngine(dev_mode=...)", "pass settings=Settings(dev=...) instead")
            if settings is not None:
                raise TypeError("Pass dev mode in settings, not both settings= and dev_mode=")
            settings = Settings(dev=dev_mode)
        self.settings = settings if settings is not None else Settings()

        if db_connection is None:
            db = self.settings.db
            db_connection = Connection(
                backend=db.backend,
                dbname=db.name,
                user=db.user,
                password=db.password.get_secret_value(),
                host=db.host,
                port=db.port,
            )

        self.api = Api()
        self.plugin_manager = PluginManager()
        self.integrations = Integrations(self.plugin_manager)
        self.db = DatabaseManager(db_connection)
        self.config_compiler = ConfigCompiler(self.db)
        self.mgmt_con_manager = ManagementConnectionManager(self.db)
        self.influxdb_settings = self.settings.influxdb
        # Nothing connects to RabbitMQ until the first job is published.
        self.jobs = JobManager(self.db, JobProducer(self.settings.rabbitmq))

        # create plugin instances.
        if assets_plugin is not None:
            self.plugin_manager.register_type_plugin("assets", assets_plugin)

        if logical_nodes_plugin is not None:
            self.plugin_manager.register_type_plugin("logical_nodes", logical_nodes_plugin)

        if sites_plugin is not None:
            self.plugin_manager.register_type_plugin("sites", sites_plugin)

        if contacts_plugin is not None:
            self.plugin_manager.register_type_plugin("contacts", contacts_plugin)

        # Create Inventory
        self.inventory = Inventory(
            db_connection=self.db,
            assets_plugin=self.plugin_manager.get_plugin_for_object_type("assets"),
            logical_nodes_plugin=self.plugin_manager.get_plugin_for_object_type("logical_nodes"),
            sites_plugin=self.plugin_manager.get_plugin_for_object_type("sites"),
            contacts_plugin=self.plugin_manager.get_plugin_for_object_type("contacts"),
            config_compiler=self.config_compiler,
            integrations=self.integrations,
            influxdb_settings=self.influxdb_settings,
        )

        # Create DeviceConfigManager
        self.device_config_manager = DeviceConfigManager(self.db, self.inventory)

        # Create LldpNeighborManager
        from acex.lldp.lldp_neighbor_manager import LldpNeighborManager

        self.lldp_neighbor_manager = LldpNeighborManager(self.db)

        # Built in create_app() from settings.credentials
        self.credential_manager = None

        self._run_migrations()

    @property
    def dev_mode(self) -> bool:
        return self.settings.dev

    def _run_migrations(self):
        """
        Apply Alembic migrations up to head, use on startup.
        """
        self.db.upgrade()

    def _build_credential_manager(self):
        from acex.credentials.credential_manager import CredentialManager

        creds = self.settings.credentials
        vault_client = None
        if creds.vault.configured:
            from acex.credentials.vault_client import VaultClient

            vault = creds.vault
            vault_client = VaultClient(
                url=vault.addr,
                token=vault.token.get_secret_value() if vault.token else None,
                role_id=vault.role_id,
                secret_id=vault.secret_id.get_secret_value() if vault.secret_id else None,
                verify=vault.verify,
            )
        key = creds.encryption_key.get_secret_value() if creds.encryption_key else None
        self.credential_manager = CredentialManager(self.db, key, vault_client=vault_client)

    def create_app(self) -> "FastAPI":
        """
        This is the method that creates the full API.

        Refuses (UnsafeConfiguration) to build an app that would be exposed
        without auth or trust every origin, unless settings.dev is set.
        """
        self.settings.check()
        self._build_credential_manager()
        self.inventory.telemetry_registry.credential_manager = self.credential_manager
        if not hasattr(self, "ai_ops_manager") and self.settings.ai_ops.enabled:
            from acex.ai_ops import AIOpsManager

            self.ai_ops_manager = AIOpsManager(settings=self.settings.ai_ops)
        return self.api.create_app(self)

    # ------------------------------------------------------------------
    # Code-level configuration: things only an integrator's app.py can express
    # ------------------------------------------------------------------

    def add_configmap_dir(self, dir_path: str):
        self.config_compiler.add_config_map_path(dir_path)

    def register_datasource_plugin(self, name: str, plugin_factory: "IntegrationPluginFactoryBase"):
        self.plugin_manager.register_generic_plugin(name, plugin_factory)

    def add_integration(self, name, integration):
        """
        Adds an integration.
        """
        print(f"Adding integration {name} with plugin: {integration}")
        self.plugin_manager.register_generic_plugin(name, integration)

    # ------------------------------------------------------------------
    # Deprecated setters. Each value now lives in Settings; these write into
    # self.settings so existing app.py files keep working for a release.
    # ------------------------------------------------------------------

    def set_encryption_key(self, key: str):
        """Deprecated: use Settings(credentials={"encryption_key": ...}) or ACEX_CREDENTIALS_ENCRYPTION_KEY."""
        from pydantic import SecretStr

        _deprecated(
            "set_encryption_key()",
            'use Settings(credentials={"encryption_key": ...}) or ACEX_CREDENTIALS_ENCRYPTION_KEY',
        )
        self.settings.credentials.encryption_key = SecretStr(key)

    def set_vault(self, url: str, token: str = None, role_id: str = None, secret_id: str = None, verify: bool = True):
        """Deprecated: use Settings(credentials={"vault": {...}}) or VAULT_*."""
        from acex.settings import VaultSettings

        _deprecated("set_vault()", 'use Settings(credentials={"vault": {...}}) or VAULT_* env vars')
        self.settings.credentials.vault = VaultSettings(
            addr=url, token=token, role_id=role_id, secret_id=secret_id, verify=verify
        )

    def set_oidc(self, issuer_url: str, audience: str = "acex", jwks_ttl: int = 3600, verify_ssl: bool = True):
        """Deprecated: use Settings(oidc={...}) or OIDC_*."""
        from acex.settings import OidcSettings

        _deprecated("set_oidc()", "use Settings(oidc={...}) or OIDC_* env vars")
        self.settings.oidc = OidcSettings(
            issuer_url=issuer_url, audience=audience, jwks_ttl=jwks_ttl, verify_ssl=verify_ssl
        )

    def add_cors_allowed_origin(self, origin: str):
        """Deprecated: use Settings(cors={"allowed_origins": [...]}) or ACEX_CORS_ALLOWED_ORIGINS."""
        _deprecated(
            "add_cors_allowed_origin()",
            'use Settings(cors={"allowed_origins": [...]}) or ACEX_CORS_ALLOWED_ORIGINS',
        )
        cors = self.settings.cors
        # The first explicit origin replaces a dev-mode "*" default.
        origins = cors.allowed_origins if "allowed_origins" in cors.model_fields_set else []
        cors.allowed_origins = [*origins, origin]

    def ai_ops(
        self,
        enabled: bool = False,
        providers: list[dict] = None,
        chains: dict[str, list[str]] = None,
        mcp_server_url: str = None,
    ):
        """Deprecated: use Settings(ai_ops=AIOpsSettings(...)) or ACEX_AI_OPS_* env vars."""
        from acex.ai_ops import AIOpsManager
        from acex.settings import AIOpsSettings

        _deprecated("ai_ops()", "use Settings(ai_ops=AIOpsSettings(...)) or ACEX_AI_OPS_* env vars")
        if not enabled:
            return None

        given = {
            "providers": {p["name"]: p for p in providers} if providers is not None else None,
            "chains": chains,
            "mcp_server_url": mcp_server_url,
        }
        settings = AIOpsSettings(**{key: value for key, value in given.items() if value is not None})
        if not settings.enabled:
            raise ValueError(
                "AI Ops is enabled, but no provider is configured. Pass providers= and chains= "
                "to ae.ai_ops(), or set ACEX_AI_OPS_* env vars (see docs/examples/ai_ops.md)."
            )
        self.settings.ai_ops = settings
        self.ai_ops_manager = AIOpsManager(settings=settings)

    def set_influxdb(self, url: str, version: str = "v3", **output):
        """Deprecated: use Settings(influxdb=InfluxDBSettings(...)) or ACEX_INFLUXDB_*.

        Replace the backend-default InfluxDB outputs with a single one. Takes
        the fields of InfluxDBOutput (token, organization, bucket, ...).
        """
        _deprecated("set_influxdb()", "use Settings(influxdb=InfluxDBSettings(...)) or ACEX_INFLUXDB_* env vars")
        self._set_primary_influxdb(url=url, version=version, **output)
        self.influxdb_settings.extra_outputs = []

    def add_influxdb(self, url: str, version: str = "v3", **output):
        """Deprecated: use Settings(influxdb=InfluxDBSettings(extra_outputs=[...])).

        Append one more backend-default InfluxDB output.
        """
        from acex.settings import InfluxDBOutput

        _deprecated("add_influxdb()", "use Settings(influxdb=InfluxDBSettings(extra_outputs=[...]))")
        if self.influxdb_settings.primary_output is None:
            self._set_primary_influxdb(url=url, version=version, **output)
        else:
            self.influxdb_settings.extra_outputs.append(InfluxDBOutput(url=url, version=version, **output))

    def _set_primary_influxdb(self, **output):
        from acex.settings import InfluxDBOutput

        # Validated as a whole output first, so a bad value is rejected
        # before anything is changed.
        primary = InfluxDBOutput(**output)
        for name, value in primary.model_dump().items():
            setattr(self.influxdb_settings, name, value)
