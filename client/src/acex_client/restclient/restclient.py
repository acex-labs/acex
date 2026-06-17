import urllib3
import requests

from acex_client.auth.provider import AuthProvider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RestClient:
    def __init__(self, api_url: str, auth: AuthProvider, verify: bool):
        self.url = api_url
        self.auth = auth
        self.verify = verify

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.auth.get_token()}"}

    def get_item(self, endpoint: str, id: int):
        url = f"{self.url}{endpoint}{id}"
        response = requests.get(url, headers=self._headers, verify=self.verify)
        if response.status_code == 200:
            data = response.json()
        else:
            print(f"{response.status_code}: {response.text}")
            data = {}
        return data

    def query_items(self, endpoint: str, params: dict = None):
        url = f"{self.url}{endpoint}"
        response = requests.get(url, headers=self._headers, params=params, verify=self.verify)
        data = response.json()
        return data
