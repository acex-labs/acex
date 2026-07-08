import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RestClient:
    def __init__(self, api_url: str, verify: bool): 
        self.url = api_url
        self.verify = verify

    def get_item(self, endpoint: str, id: int): 
        url = f"{self.url}{endpoint}{id}"
        response = requests.get(url, verify=self.verify)
        if response.status_code == 200:
            data = response.json()
        else:
            data = {}
        return data

    def query_items(self, endpoint: str, params: dict = None):
        url = f"{self.url}{endpoint}"
        response = requests.get(url, params=params, verify=self.verify)
        data = response.json()
        return data
