import os
from acex.constants import DEFAULT_ROOT_DIR, BASE_URL

from fastapi import FastAPI, APIRouter
from acex.api.api import Api
from acex.inventory import Inventory
from acex.plugins.integrations import IntegrationPluginBase, IntegrationPluginFactoryBase
from acex.plugins.integrations import IntegrationPluginBase, IntegrationPluginFactoryBase

from acex.plugins.adaptors import DatasourcePluginAdapter
from acex.database import Connection, DatabaseManager
from acex.compilers import ConfigCompiler
from acex.models import Asset, LogicalNode
from acex.plugins import PluginManager
from acex.device_configs import DeviceConfigManager
from acex.management_connections import ManagementConnectionManager


class Integrations(): 

    def __init__(self, plugin_manager: 'PluginManager'):
        """
        Datasources fungerar som en brygga till PluginManager för att hantera
        både objektstyp-specifika plugins och generiska datasources.
        """
        self._plugin_manager = plugin_manager

    def add_datasource(self, name: str, plugin_factory: IntegrationPluginFactoryBase):
        """
        Lägg till en plugin factory som en generisk datasource.
        Detta gör att samma factory kan användas både för specifika objektstyper
        och som en generisk datasource.
        """
        self._plugin_manager.register_generic_plugin(name, plugin_factory)

    def get_datasource(self, name: str, use_adapter: bool = False) -> IntegrationPluginBase:
        """
        Hämta en plugin instans för en generisk datasource.
        """
        plugin = self._plugin_manager.get_generic_plugin(name)
        print(f"Hämtar plug: {plugin}")
        return DatasourcePluginAdapter(plugin)
    
    def get_datasource_with_adapter(self, name: str) -> DatasourcePluginAdapter:
        """
        Hämta en plugin instans wrappat i DatasourcePluginAdapter.
        """
        plugin = self._plugin_manager.get_generic_plugin(name)
        return DatasourcePluginAdapter(plugin)
    
    def list_datasources(self) -> list[str]:
        """
        Lista alla registrerade generiska datasources.
        """
        return list(self._plugin_manager._generic_plugin_map.keys())
    
    def __getattr__(self, name: str):
        """
        Dynamiskt skapa plugin instanser när de efterfrågas.
        T.ex. data.datasources.ipam returnerar en ipam plugin instans.
        """
        try:
            return self.get_datasource_with_adapter(name)
        except Exception as e:
            raise AttributeError(f"Datasource '{name}' not found. Available datasources: {self.list_datasources()}") from e


class AutomationEngine: 

    def __init__(
            self,
            db_connection:Connection|None = None,
            assets_plugin:IntegrationPluginBase|None = None,
            logical_nodes_plugin:IntegrationPluginBase|None = None
        ):
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


    def create_app(self) -> FastAPI:
        """
        This is the method that creates the full API.
        """
        return self.api.create_app(self)

    def add_configmap_dir(self, dir_path: str):
        self.config_compiler.add_config_map_path(dir_path)

    def add_cors_allowed_origin(self, origin: str):
        self.cors_settings_default = False
        self.cors_allowed_origins.append(origin)

    def register_datasource_plugin(self, name: str, plugin_factory: IntegrationPluginFactoryBase): 
        self.plugin_manager.register_generic_plugin(name, plugin_factory)
    
    def add_integration(self, name, integration ):
        """
        Adds an integration. 
        """
        print(f"Adding integration {name} with plugin: {integration}")
        self.plugin_manager.register_generic_plugin(name, integration)