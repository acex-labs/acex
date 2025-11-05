from acex.plugins.integrations import IntegrationPluginBase, IntegrationPluginFactoryBase
from acex.plugins.adaptors import DatasourcePluginAdapter

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
