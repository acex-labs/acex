import urllib3
import requests
import requests.auth

from acex_client.auth.provider import AuthProvider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class _BearerAuth(requests.auth.AuthBase):
    def __init__(self, auth: AuthProvider):
        self._auth = auth

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self._auth.get_token()}"
        return r


class RestClient:
    def __init__(self, api_url: str, auth: AuthProvider, verify: bool):
        self.url = api_url
        self._session = requests.Session()
        self._session.auth = _BearerAuth(auth)
        self._session.verify = verify

    def _url(self, endpoint: str, id=None) -> str:
        if id is not None:
            return f"{self.url}{endpoint}{id}"
        return f"{self.url}{endpoint}"

    def get_item(self, endpoint: str, id) -> dict | None:
        response = self._session.get(self._url(endpoint, id))
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def query_items(self, endpoint: str, params: dict = None) -> dict | list:
        response = self._session.get(self._url(endpoint), params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, json: dict) -> dict:
        response = self._session.post(self._url(endpoint), json=json)
        response.raise_for_status()
        return response.json()

    def patch(self, endpoint: str, id, json: dict) -> dict:
        response = self._session.patch(self._url(endpoint, id), json=json)
        response.raise_for_status()
        return response.json()

    def delete(self, endpoint: str, id) -> None:
        response = self._session.delete(self._url(endpoint, id))
        response.raise_for_status()
