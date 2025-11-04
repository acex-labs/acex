from .integration_plugin_base import IntegrationPluginBase
from .integration_plugin_factory_base import IntegrationPluginFactoryBase
from acex.utils import RestClient
from acex.models import AssetResponse, LogicalNodeResponse

import json
from requests import Response


# TODO: Fixa en egen hantering av response formatering. 
# Behöver få med:
# - DatasourceValue
# - Metadata
# - Modellering och validering av standardobjekt
# - Hämta interface uppmappade i netbox för assets? 


class Netbox(IntegrationPluginFactoryBase): 

    def __init__(self, url: str, token: str, verify_ssl: bool = True):
        """
        Used to define the connection to netbox. This is a factory class
        that will create a NetboxPluginInstance for each model used.
        """
        self.base_url = f"{url}api/"
        self.token = token
        self.rest = RestClient(self.base_url, verify_ssl=verify_ssl)
        self.rest.add_header("Authorization", f"Token {self.token}")
        self.rest.add_header("Content-Type", "application/json")


    def create_plugin(self, type: str|None = None) -> 'NetboxPlugin':
        """
        Create a plugin instance for a specific model.
        If no type is selected, generic plugin is returned.
        :param type: string representing the model/type to retreive.
        :return: An instance of NetboxPlugin.
        """
        if type is not None:
            return NetboxObjectPlugin(type, restclient=self.rest)
        else:
            return NetboxGenericPlugin(restclient=self.rest)


class NetboxGenericPlugin(IntegrationPluginBase):
    RESOURCE_TYPES = [
        "prefixes",
        "ip_addresses"
    ]

    DATA_TYPES= [
        "ip_addresses"
    ]

    def __init__(self, restclient: RestClient):
        self.rest = restclient
    
    def __repr__(self):
        return f"{self.__class__.__name__}:{self.rest.base_url}"

    def _type_to_endpoint(self, kind) -> str:
        """
        Maps the endpoint for a given object kind
        """
        match kind:
            case "ip_addresses":
                return "ipam/ip-addresses"

    def _get_output_from_response(self, kind, json_dict: dict):
        """
        Extract data from a json response based on object type.
        """
        match kind:
            case "ip_addresses":
                return json_dict["address"]

    def query(self, kind: str, query: dict): 
        endpoint = self._type_to_endpoint(kind)
        if "id" in query:
            endpoint = endpoint + f"/{query["id"]}"
        data = self.rest.get(endpoint, query).json()
        return self._get_output_from_response(kind, data)


class NetboxObjectPlugin(IntegrationPluginBase):
    """
    The actual plugin instance that will be used by the adapter in the
    inventory. Will be instanciated for each model used. Using the Netbox class
    to define the connection details.
    """
    PLUGIN_NAME = "netbox"
    OBJECT_TYPES = ["assets", "logical_nodes"]
    ENTITY_ENDPOINTS = {
        "assets": "dcim/devices/",
        "logical_nodes": "dcim/devices/",
    }
    OBJ_CLASS_MAP = {
        "assets": AssetResponse,
        "logical_nodes": LogicalNodeResponse
    }

    def __init__(self, type:str, restclient: RestClient):
        """
        Initialize the Netbox datasource plugin with a Netbox API client.
        :param url: The base URL of the Netbox instance.
        :param token: The API token for authentication.
        :param verify_ssl: Whether to verify SSL certificates (default is True).
        """
        self.rest = restclient
        self.type = type


    def _get_endpoint(self, id: str = None, filters: dict | None = None) -> str:
        """
        Return endpoint for the object type.
        """
        url =  self.__class__.ENTITY_ENDPOINTS.get(self.type, "")
        if id is not None:
            url += f"{id}/"
        elif filters:
            url += "?" + "&".join(f"{k}={v}" for k, v in filters.items())
        return url

    def _format_model(self, json_data: dict):
        model = self.__class__.OBJ_CLASS_MAP.get(self.type)
        return model(**json_data)


    def get(self, id: str):
        response = self.rest.get(self._get_endpoint(id=id))
        response = self._format_model(response.json())
        print(response.json())
        return response


    def query(self, filters: dict | None = None) -> list:
        response = []
        nb_response = self.rest.get(self._get_endpoint(filters=filters))
        for i in nb_response.json()["results"]:
            response.append(self._format_model(i))
        return response
