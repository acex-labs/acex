import requests


class RestClient:
    def __init__(self, api_url: str): 
        self.url = api_url

    def get_item(self, endpoint: str, id: int): 
        url = f"{self.url}{endpoint}{id}"
        response = requests.get(url)
        data = response.json()
        return data

    def query_items(self, endpoint: str, params: dict = {}, limit: int = 100, cursor: str = None): 
        url = f"{self.url}{endpoint}"
        response = requests.get(url)
        data = response.json()
        return data
