from importlib.metadata import entry_points
import subprocess, sys
from acex_client.models.models import LogicalNode, Ned


class Neds:

    def __init__(
        self,
        rest_client
        ):
        self.rest = rest_client

    def _url_for_wheel(self, ned: Ned) -> str:
        """
        Get url for fetching specific ned from api. 
        """
        url = f"{self.rest.url}/neds/download/{ned.filename}"
        return url
    
    def _install_wheel_from_api(self, ned: Ned):
        """
        Installs a NED from the central API. 
        """
        url = self._url_for_wheel(ned)
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", url
        ])

    def get_all(self):
        """
        List all NEDs installed centrally.
        """
        response = []
        ep = "/neds/"
        api_response = self.rest.query_items(ep)
        for ned in api_response:
            response.append(Ned(**ned))
        return response

    def install(self, ned:Ned): 
        """
        Downloads ned from api and installs the whl.
        """
        print(f"Installing ned: {ned.name} - {ned.package_name}")
        self._install_wheel_from_api(ned)


    def check_status(self, ned: Ned): 
        """
        Check if given package and version is installed. 
        """
        for entry_point in entry_points(group="acex.neds"):
            if entry_point.dist.name == ned.package_name:
                if entry_point.dist.version == ned.version:
                    return True 
        return False


    def get_missing(self):
        """
        Return a list of all neds declared at the API that are not
        installed locally. 
        """
        missing = []
        neds = self.get_all()
        for ned in neds:
            if self.check_status(ned) is False:
                missing.append(ned)
        return missing
