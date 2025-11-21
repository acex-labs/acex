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
            return NetboxMockPlugin(type, restclient=self.rest)
        else:
            return NetboxMockPlugin(restclient=self.rest)


class NetboxMockPlugin(IntegrationPluginBase):
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
        return "192.0.2.1/24"

