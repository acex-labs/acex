import requests
from models.models import ComposedConfiguration
from models.models import LogicalNode, Ned
from restclient.restclient import RestClient

from .logical_nodes import LogicalNodes
from .neds import Neds


class Acex: 
    def __init__(
        self,
        baseurl: str = "http://127.0.0.1/",
        api_ver: int = 1
        ):
        self.api_url = f"{baseurl}api/v{api_ver}"
        self.rest = RestClient(api_url = self.api_url)

        self.logical_nodes = LogicalNodes(self.rest)
        self.neds = Neds(self.rest)

