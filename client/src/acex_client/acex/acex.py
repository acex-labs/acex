import requests
from models.models import ComposedConfiguration
from models.models import LogicalNode
from restclient.restclient import RestClient

class Acex: 
    def __init__(
        self,
        baseurl: str = "http://127.0.0.1/",
        api_ver: int = 1
        ):
        self.api_url = f"{baseurl}api/v{api_ver}"
        self.rest = RestClient(api_url = self.api_url)

    
    def test(self):
        t = requests.get(f"{self.api_url}/inventory/logical_nodes/1")
        t = t.json()

        cc = ComposedConfiguration(**t["configuration"])


    def logical_nodes(self):
        response = []
        ep = "/inventory/logical_nodes/"
        api_response = self.rest.query_items(ep)

        for ln in api_response:
            response.append(LogicalNode(**ln))

        return response