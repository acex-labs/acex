from importlib.metadata import entry_points
from urllib.parse import urlparse
import subprocess, sys
from acex_client.models.generated_models import LogicalNode, Ned
from .resource_base import Resource


class Neds(Resource):

    ENDPOINT =  "/neds/"
    RESPONSE_MODEL_SINGLE = Ned
    RESPONSE_MODEL_LIST = Ned


    def __init__(self, rest_client):
        self.rest = rest_client
        self._drivers = None

    @property
    def drivers(self):
        if self._drivers is None:
            self._drivers = {}
            for entry_point in entry_points(group="acex.neds"):
                try:
                    _class = entry_point.load()
                    instance = _class()
                    version = entry_point.dist.version
                    self._drivers[_class.__name__] = {
                        "instance": instance,
                        "version": version,
                        "package_name": entry_point.dist.name,
                    }
                except Exception as e:
                    print(f"Error when loading {entry_point.name}: {e}")
        return self._drivers

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
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
        if not self.rest.verify:
            host = urlparse(url).hostname
            if host:
                cmd += ["--trusted-host", host]
        cmd.append(url)
        subprocess.check_call(cmd)

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


    def get_driver(self, driver_name: str):
        """
        Returns an instance based on name.
        """
        return self.drivers.get(driver_name)


    def get_driver_instance(self, driver_name: str):
        """
        Returns an instance based on name.
        """
        return self.drivers.get(driver_name).get('instance')
