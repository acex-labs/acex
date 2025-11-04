import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Stäng av SSL verification warnings
urllib3.disable_warnings(InsecureRequestWarning)


class RestClient:
    def __init__(self, base_url: str, verify_ssl: bool = True):
        self.base_url = base_url
        self.headers = {}
        self.verify_ssl = verify_ssl

    def _create_request_url(self, endpoint: str):
        return f"{self.base_url}{endpoint}"

    def request(self, method: str, endpoint: str, data=None, params=None):
        print(f"restclient: {method.upper()} {self.base_url}{endpoint}")
        url = self._create_request_url(endpoint)
        response = requests.request(method, url, headers=self.headers, json=data, params=params, verify=self.verify_ssl)
        return response

    def add_header(self, key: str, value: str):
        self.headers[key] = value

    def get(self, endpoint: str, params=None):
        return self.request("GET", endpoint, params=params)

    def post(self, endpoint: str, data=None, json=None):
        return self.request("POST", endpoint, data=data, json=json)

    def put(self, endpoint: str, data=None):
        # Implementation of PUT request
        pass

    def delete(self, endpoint: str):
        # Implementation of DELETE request
        pass