from .adapter_base import AdapterBase
from acex.models import Asset
from acex.models import ExternalValue
import json

class ProxyDatasource:
    """
    Proxy object to enable dotted syntax and query for 
    datasources within the plugin by referencing
    the resource name with ...{plugin}.data.{resource_name}({})
    """
    
    def __init__(self, plugin_adapter):
        self._plugin_adapter = plugin_adapter

    def __getattr__(self, resource_name: str):
        if resource_name not in self._plugin_adapter.plugin.DATA_TYPES:
            raise Exception(f"Resource type '{resource_name}' not defined in plugin: {self._plugin_adapter.plugin}")
        return lambda query: self._plugin_adapter._handle_datasource(resource_name, query)

class ProxyResource:
    """
    Proxy object to enable dotted syntax and query for 
    resources within the plugin by referencing
    the resource name with ...{plugin}.resource.{resource_name}({})
    """
    
    def __init__(self, plugin):
        self._plugin = plugin

    def __getattr__(self, resource_name: str):
        if resource_name not in self._plugin.RESOURCE_TYPES:
            raise Exception(f"Resource type '{resource_name}' not defined in plugin: {self._plugin}")
        return lambda query: self._plugin._handle_resource(resource_name, query)


class DatasourcePluginAdapter(AdapterBase):
    """
    Adapter säkerställer att rätt metodnamn används och
    inget annat. 

    Berikar respons med rätt responsetyper. 
    """

    def __init__(self, plugin):
        super().__init__(plugin)

    def __repr__(self):
        return f"d: {self.plugin}"


    @property
    def data(self):
        return ProxyDatasource(self)

    @property
    def resource(self):
        return ProxyResource(self)

    def _handle_datasource(self, resource_name: str, query: dict):
        data = self.query(resource_name, query)
        return data


    def _handle_resource(self, resource_name: str, query: dict):
        # TODO: Fixa create om inte state finns!
        data = self.plugin.query(resource_name, query)

        # IF NO STATE;
        # data = self.create()

        return "99.99.99.99/30"
        return data


    def create(self, asset: Asset): 
        if hasattr(self.plugin, "create"):
            return getattr(self.plugin, "create")(asset)
        raise NotImplementedError("Plugin does not support create operation")

    def get(self, kind: str, id: str): 
        if hasattr(self.plugin, "get"):
            return getattr(self.plugin, "get")(id)
        raise NotImplementedError("Plugin does not support get operation")

    def query(self, kind: str, filters: dict = None): 
        """
        The query method of the adapter will not actually 
        run the callable from the plugin, but construct an
        instance of an ExternalValue, to which all query parameters
        and details about the plugin and the actual Callable 
        is placed. The actual resolvement of the values are done 
        later by the configCompiler.
        """

        # Using the function from the very plugin
        func = getattr(self.plugin, "query")

        ev = ExternalValue(
            ev_type = "data",
            query=json.dumps(filters),
            value="_known after resolve_",
            kind=kind,
            plugin=str(self.plugin)
        )

        # Tilldela _callable efter objektskapande för PrivateAttr
        ev._callable = func
        return ev


    def update(self, asset: Asset): 
        if hasattr(self.plugin, "update"):
            return getattr(self.plugin, "update")(asset)
        raise NotImplementedError("Plugin does not support update operation")

    def delete(self, id: str): 
        if hasattr(self.plugin, "delete"):
            return getattr(self.plugin, "delete")(id)
        raise NotImplementedError("Plugin does not support delete operation")
