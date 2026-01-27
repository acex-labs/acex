import requests
from acex_client.models.models import ComposedConfiguration
from acex_client.models.models import LogicalNode, Ned
from acex_client.restclient.restclient import RestClient

from .resources.assets import Assets
from .resources.logical_nodes import LogicalNodes
from .resources.node_instances import NodeInstances
from .resources.neds import Neds


class Acex: 
    def __init__(
            self,
            baseurl: str = "http://127.0.0.1/",
            api_ver: int = 1,
            verify: bool = True
        ):

        self.api_url = f"{baseurl}api/v{api_ver}"
        self.rest = RestClient(api_url = self.api_url, verify=verify)

        self.assets = Assets(self.rest)
        self.logical_nodes = LogicalNodes(self.rest)
        self.node_instances = NodeInstances(self.rest)
        self.neds = Neds(self.rest)

