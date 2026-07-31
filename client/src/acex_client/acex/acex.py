from acex_client.auth import AuthProvider, create_auth_provider
from acex_client.restclient.restclient import RestClient
from acex_devkit.configdiffer.configdiffer import ConfigDiffer

from .resources.node_instances import NodeInstances
from .resources.credentials import Credential
from .resources.management_connections import ManagementConnections



class Acex:
    def __init__(
            self,
            baseurl: str = "http://127.0.0.1/",
            api_ver: int = 1,
            verify: bool = True,
            auth: AuthProvider | None = None,
        ):
        self.api_url = f"{baseurl}api/v{api_ver}"
        resolved_auth = auth or create_auth_provider()
        self.rest = RestClient(api_url=self.api_url, auth=resolved_auth, verify=verify)

        self.node_instances = NodeInstances(self.rest)
        self.credentials = Credential(self.rest)
        self.management_connections = ManagementConnections(self.rest)
        self.differ = ConfigDiffer()
