import requests
from models.models import ComposedConfiguration
from restclient.restclient import RestClient

class Acex: 
    def __init__(
        self,
        baseurl: str = "http://127.0.0.1/",
        api_ver: int = 1
    ):
        self.api_url = f"{baseurl}api/v{api_ver}"

    def test(self):
        t = requests.get(f"{self.api_url}/inventory/logical_nodes/1")
        t = t.json()

        cc = ComposedConfiguration(**t["configuration"])


