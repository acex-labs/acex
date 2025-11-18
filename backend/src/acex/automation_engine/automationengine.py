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
            logical_nodes_plugin:"IntegrationPluginBase|None" = None
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
        self.device_config_manager = DeviceConfigManager(self.db)
        self.mgmt_con_manager = ManagementConnectionManager(self.db)
        self.cors_settings_default = True
        self.cors_allowed_origins = []
        
        # create plugin instances.
        if assets_plugin is not None:
            self.plugin_manager.register_type_plugin("assets", assets_plugin)

        if logical_nodes_plugin is not None:
            self.plugin_manager.register_type_plugin("logical_nodes", logical_nodes_plugin)


        self.inventory = Inventory(
            db_connection = self.db,
            assets_plugin=self.plugin_manager.get_plugin_for_object_type("assets"),
            logical_nodes_plugin=self.plugin_manager.get_plugin_for_object_type("logical_nodes"),
            config_compiler=self.config_compiler,
            integrations=self.integrations,
        )
        self._create_db_tables()
        
    def _create_db_tables(self):
        """
        Create tables if not exist, use on startup.
        """
        self.db.create_tables()


    def create_app(self) -> "FastAPI":
        """
        This is the method that creates the full API.
        """
        return self.api.create_app(self)

    def ai_ops(
        self,
        enabled: bool = False,
        api_key: str = None,
        base_url: str = None,
        mcp_server_url: str = None
    ): 
        if enabled is True:
            if api_key is None or base_url is None or mcp_server_url is None:
                print("AI OPs is enabled, but missing parameters!")
                return None
            # Lazy import - only load when AI ops is actually enabled
            from acex.ai_ops import AIOpsManager
            self.ai_ops_manager = AIOpsManager(api_key=api_key, base_url=base_url, mcp_server_url=mcp_server_url)

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