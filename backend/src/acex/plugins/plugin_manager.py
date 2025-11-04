from typing import Dict, Type, Optional
from acex.plugins.integrations.integration_plugin_factory_base import IntegrationPluginFactoryBase, IntegrationPluginBase

class PluginManager:
    """
    Hanterar registrering och hämtning av både specifika och generiska plugins.
    """
    def __init__(self):
        # En factory per objekt-typ (men samma factory kan användas för flera typer)
        self._object_type_map: Dict[str, IntegrationPluginFactoryBase] = {}

        # En factory per generiskt namn
        self._generic_plugin_map: Dict[str, IntegrationPluginFactoryBase] = {}

    def register_type_plugin(self, object_type: str, factory: IntegrationPluginFactoryBase):
        """
        Registrera en factory för en specifik objekt-typ (t.ex. "asset").
        """
        self._object_type_map[object_type] = factory

    def register_generic_plugin(self, plugin_name: str, factory: IntegrationPluginFactoryBase):
        """
        Registrera en factory för ett generiskt namn (t.ex. "netbox").
        """
        self._generic_plugin_map[plugin_name] = factory.create_plugin()

    def get_plugin_for_object_type(self, obj_type: str) -> Optional[IntegrationPluginBase]:
        plugin = self._object_type_map.get(obj_type)
        return None

    def get_generic_plugin(self, plugin_name: str,) -> Optional[IntegrationPluginBase]:
        plugin = self._generic_plugin_map.get(plugin_name)
        return plugin

