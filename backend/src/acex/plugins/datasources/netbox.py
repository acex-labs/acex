from .datasource_plugin_base import DatasourcePluginBase
from .datasource_plugin_factory_base import PluginFactoryBase

from acex.utils import RestClient
from acex.models import Asset, AssetResponse, LogicalNode, Node, NodeResponse, LogicalNodeResponse
from acex.configuration.datasource_value import DataSourceValue

from typing import Type
from pydantic import BaseModel

import json


class Netbox(): 

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


    def create_plugin(self, model: Type[BaseModel]) -> 'NetboxPlugin':
        """
        Create a plugin instance for a specific model.
        :param model: The Pydantic model class to use for the plugin.
        :return: An instance of NetboxPlugin.
        """
        return NetboxPlugin(model=model, restclient=self.rest)


class NetboxPlugin:
    """
    The actual plugin instance that will be used by the adapter in the
    inventory. Will be instanciated for each model used. Using the Netbox class
    to define the connection details.
    """

    ENTITY_ENDPOINTS = {
        Asset: "dcim/devices/",
        LogicalNode: "dcim/devices/",
    }

    def __init__(self, model: Type[BaseModel], restclient: RestClient):
        """
        Initialize the Netbox datasource plugin with a Netbox API client.
        :param url: The base URL of the Netbox instance.
        :param token: The API token for authentication.
        :param verify_ssl: Whether to verify SSL certificates (default is True).
        """
        self.rest = restclient
        self.model = model


    def _get_ep(self, id: str = None, filters: dict | None = None) -> str:
        """
        Return endpoint for the model.
        """
        url =  self.__class__.ENTITY_ENDPOINTS.get(self.model, "")
        if id is not None:
            url += f"{id}/"
        elif filters:
            url += "?" + "&".join(f"{k}={v}" for k, v in filters.items())
        return url


    def _build_asset_model(self, data: dict) -> Asset:
        """
        Build an Asset model instance from raw data.
        :param data: Raw data from Netbox API.
        :return: An Asset model instance.
        """
        # Fetch interfaces
        interfaces = []
        intf_response = self.rest.get(f"dcim/interfaces/?device_id={data.get('id')}")
        for interface in intf_response.json().get("results", []):
            if interface.get("type", {}).get("value") != "virtual":
                interfaces.append(({
                    "name": interface.get("name"),
                    "type": interface.get("type", {}).get("value"),
                    "mac_address": interface.get("mac_address"),
                    "speed_kbps": interface.get("speed")
                }))

        return AssetResponse(
            id=data.get("id"),
            vendor=data.get("device_type", {}).get("manufacturer", {}).get("name"),
            os=data.get("platform", {}).get("name"),
            serial_number=data.get("serial"),
            ned_id=data.get("custom_fields", {}).get("ned_id"),
            hardware_model=data.get("device_type", {}).get("model"),
            interfaces=interfaces
        )

    def _build_logical_node_model(self, data: dict) -> LogicalNode:
        """
        Build a LogicalNode model instance from raw data.
        :param data: Raw data from Netbox API.
        :return: A LogicalNode model instance.
        """
    

        return LogicalNodeResponse(
            id=data.get("id"),
            hostname=data.get("name"),
            role=data.get("role", {}).get("name"),
            site=data.get("site", {}).get("name"),
            # interfaces=interfaces
        )


    def _build_model(self, data: dict, model: Type[BaseModel] = None) -> BaseModel:
        """
        Build a correct model instance with data from netbox api.
        Input data is a raw dict from netbox, and the model is the pydantic model
        used in the rest of ACE.
        """
        if self.model is Asset:
            return self._build_asset_model(data)
        elif self.model is LogicalNode:
            return self._build_logical_node_model(data)
        return {}


    def get(self, id: str):
        response = self.rest.get(self._get_ep(id=id))
        return self._build_model(response.json())

    # def create(self, data: BaseModel):
    #     return {}


    def query(self, filters: dict | None = None) -> list:
        response = self.rest.get(self._get_ep(filters=filters))
        for d in response.json().get("results", []):
            yield self._build_model(d)


    # def update(self, id: str, data: BaseModel):
    #     return {}

    # def delete(self, id: str):
    #     return {}

