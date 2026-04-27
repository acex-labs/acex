import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from acex.plugins.integrations import IntegrationPluginBase, IntegrationPluginFactoryBase
    from acex.database import Connection


class AutomationEngine: 

    def __init__(
            self,
            db_connection:"Connection|None" = None,
            assets_plugin:"IntegrationPluginBase|None" = None,
            logical_nodes_plugin:"IntegrationPluginBase|None" = None,
            sites_plugin:"IntegrationPluginBase|None" = None,
            contacts_plugin:"IntegrationPluginBase|None" = None
        ):
        # Lazy imports - only load when AutomationEngine is instantiated
        from acex.api.api import Api
        from acex.plugins import PluginManager
        from acex.database import DatabaseManager
        from acex.compilers import ConfigCompiler
        from acex.device_configs import DeviceConfigManager
        from acex.management_connections import ManagementConnectionManager
        from acex.automation_engine.integrations import Integrations
        from acex.inventory import Inventory
        
        self.api = Api()
        self.plugin_manager = PluginManager()
        self.integrations = Integrations(self.plugin_manager)
        self.db = DatabaseManager(db_connection)
        self.config_compiler = ConfigCompiler(self.db)
        self.mgmt_con_manager = ManagementConnectionManager(self.db)
        self.cors_settings_default = True
        self.cors_allowed_origins = []
        
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
            db_connection = self.db,
            assets_plugin=self.plugin_manager.get_plugin_for_object_type("assets"),
            logical_nodes_plugin=self.plugin_manager.get_plugin_for_object_type("logical_nodes"),
            sites_plugin=self.plugin_manager.get_plugin_for_object_type("sites"),
            contacts_plugin=self.plugin_manager.get_plugin_for_object_type("contacts"),
            config_compiler=self.config_compiler,
            integrations=self.integrations,
        )
        
        # Create DeviceConfigManager
        self.device_config_manager = DeviceConfigManager(self.db, self.inventory)

        # Create LldpNeighborManager
        from acex.lldp.lldp_neighbor_manager import LldpNeighborManager
        self.lldp_neighbor_manager = LldpNeighborManager(self.db)

        # Create CredentialManager
        from acex.credentials.credential_manager import CredentialManager
        self._encryption_key = None
        self._vault_client = None
        self.credential_manager = None  # initialized in set_encryption_key() or lazily

        self._create_db_tables()
        
    def _create_db_tables(self):
        """
        Create tables if not exist, use on startup.
        """
        self.db.create_tables()


    def _ensure_credential_manager(self):
        """Lazily initialize CredentialManager from env var if not set via set_encryption_key()."""
        if self.credential_manager is None:
            from acex.credentials.credential_manager import CredentialManager
            self.credential_manager = CredentialManager(self.db, self._encryption_key, vault_client=self._vault_client)
        elif self._vault_client and not self.credential_manager._vault:
            self.credential_manager._vault = self._vault_client

    def set_encryption_key(self, key: str):
        """Set the encryption key for credential storage. Call before create_app()."""
        import logging
        logging.getLogger("acex").warning(
            "Encryption key set via code — do NOT use this in production. "
            "Use the ACEX_ENCRYPTION_KEY environment variable instead."
        )
        from acex.credentials.credential_manager import CredentialManager
        self._encryption_key = key
        self.credential_manager = CredentialManager(self.db, key)

    def set_vault(self, url: str, token: str = None, role_id: str = None, secret_id: str = None, verify: bool = True):
        """Configure HashiCorp Vault for credential storage. Call before create_app()."""
        from acex.credentials.vault_client import VaultClient
        self._vault_client = VaultClient(url=url, token=token, role_id=role_id, secret_id=secret_id, verify=verify)

    def create_app(self) -> "FastAPI":
        """
        This is the method that creates the full API.
        """
        self._ensure_credential_manager()
        return self.api.create_app(self)

    def ai_ops(
        self,
        enabled: bool = False,
        api_key: str = None,
        base_url: str = None,
        mcp_server_url: str = None,
        model: str = "openai/gpt-oss-120b"
    ):
        if enabled is True:
            if api_key is None or base_url is None or mcp_server_url is None:
                print("AI OPs is enabled, but missing parameters!")
                return None
            # Lazy import - only load when AI ops is actually enabled
            from acex.ai_ops import AIOpsManager
            self.ai_ops_manager = AIOpsManager(api_key=api_key, base_url=base_url, mcp_server_url=mcp_server_url, model=model)

    def add_configmap_dir(self, dir_path: str):
        self.config_compiler.add_config_map_path(dir_path)

    def add_cors_allowed_origin(self, origin: str):
        self.cors_settings_default = False
        self.cors_allowed_origins.append(origin)

    def register_datasource_plugin(self, name: str, plugin_factory: "IntegrationPluginFactoryBase"): 
        self.plugin_manager.register_generic_plugin(name, plugin_factory)
    
    def add_integration(self, name, integration ):
        """
        Adds an integration. 
        """
        print(f"Adding integration {name} with plugin: {integration}")
        self.plugin_manager.register_generic_plugin(name, integration)