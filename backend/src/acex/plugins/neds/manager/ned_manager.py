import importlib
import pkgutil
from typing import Dict, Type
from importlib.metadata import entry_points
from acex.constants import NED_WHEEL_DIR, DEFAULT_DRIVERS
from acex.plugins.neds.core import NetworkElementDriver
from acex.models.ned import Ned

import subprocess
import sys
from pathlib import Path


class NEDManager:
    def __init__(self):

        self.driver_dir = Path.cwd() / NED_WHEEL_DIR # TODO: Fix a more robust way to discover project root. or just be run at specifik cli command
        self.driver_dir.mkdir(parents=True, exist_ok=True)
        self.drivers: Dict[str, list[NetworkElementDriver]] = {}

        # All driver specs saved here.
        self.driver_specs = []
        for driver in DEFAULT_DRIVERS:
            self.driver_specs.append(driver)

        # Load all installed drivers
        # self.load_drivers()



    def _build_spec(self, package: str, version: str) -> str:
        if version == "latest":
            return package
        # om version innehåller operator (> , >= , < , <= , ==) så lämna som den är
        operators = ["<=", ">=", ">", "<", "==", "~=", "!="]
        if any(op in version for op in operators):
            return f"{package}{version}"
        # annars tolka som exakt version
        return f"{package}=={version}"


    def _install_whl(self, whl_path: Path):
        subprocess.run([
            "python", "-m", "pip", "install", str(whl_path)
        ], check=True)

    def download_and_install_neds_in_specs(self):
        for driver in self.driver_specs:
            self._download_driver_whl(**driver)

    def _download_driver_whl(self, package: str, version: str, source: str = "pypi"):
        """
        Downloads driver from external source, such as pypi, and places
        whl in a local folder for later distribution via API, and local
        install. 
        """
        spec = self._build_spec(package, version)
        print(f"Downloading: {spec}")
        subprocess.run([
            "python", "-m", "pip", "download", spec,
            "--only-binary=:all:",
            "--dest", str(self.driver_dir)
        ], check=True)

        # find downloaded wheel
        pattern = f"{package.replace('-', '_')}*.whl"  # pip använder _ i modulnamn ibland
        whl_files = list(self.driver_dir.glob(pattern))
        if not whl_files:
            raise FileNotFoundError(f"No wheel found for {spec} in {self.driver_dir}")
        
        # install first if many
        whl_path = whl_files[0] 
        print(f"Installing wheel: {whl_path}")

        # Installera
        self._install_whl(whl_path)

    def load_drivers(self):
        """Ladda externa drivrutiner via entry_points."""

        for entry_point in entry_points(group="acex.neds"):
            try:
                klass = entry_point.load()
                instance = klass()
                version = entry_point.dist.version 
                self.drivers[klass.__name__] = {
                    "instance": instance,
                    "version": version,
                    "package_name": entry_point.dist.name
                }
            except Exception as e:
                print(f"Fel vid laddning av {entry_point.name}: {e}")

        print("Installed neds:")
        for d in self.drivers:
            print(f" - {d}")

    def driver_download_path(self, driver_name: str) -> NetworkElementDriver:
        """Returnera sökvägen till .whl-filen för en installerad drivrutin."""
        ned = self.drivers.get(driver_name)
        if ned is None:
            return None

        version = ned.get("version")
        package_name = ned.get('package_name')
        pattern = f"{package_name.replace('-', '_')}-{version}-*.whl"
        matches = list(self.driver_dir.glob(pattern))

        if not matches:
            return None
        return str(matches[0])

    def driver_filename(self, driver_name):
        """ Returnera bara filnamnet på driverns whl """
        full_path = self.driver_download_path(driver_name)
        filename = full_path.split('/')[-1]
        return filename

    def get_driver_info(self, driver_name: str) -> NetworkElementDriver:
        """Hämta en drivrutinsinstans efter namn"""
        ned = self.drivers.get(driver_name)

        if ned is None:
            return None

        filename = self.driver_filename(driver_name)
        ned_instance = ned["instance"]
        response = {
            "name": driver_name,
            "version": ned.get("version"),
            "package_name": ned.get('package_name'),
            "description": type(ned_instance).__doc__,
            "filename": filename
        }

        return response

    def get_driver_instance(self, driver_name:str):
        """
        Returns an instance of the driver class based on name.
        Checks for installed driver based on entrypoint and then name
        of the class. 
        """
        for entry_point in entry_points(group="acex.neds"):
            print()
            if entry_point.value.split(":")[-1] == driver_name:
                return entry_point.load()()

    def list_drivers(self) -> list[dict]:
        """Returnera en lista över tillgängliga drivrutinsnamn."""
        result = []
        for key, driver_data in self.drivers.items():
                driver = driver_data["instance"]
                kind = type(driver)
                filename = self.driver_filename(key)
                info = {
                    "name": key,
                    "version": driver_data.get("version", "n/a"),
                    "package_name": driver_data.get('package_name'),
                    "description": kind.__doc__ or "n/a",
                    "filename": filename
                }
                result.append(info)
        return result


    def _install_whl(self, whl_path: Path):
        subprocess.run([
            "python", "-m", "pip", "install", str(whl_path)
        ], check=True)

    def download_and_install_neds_in_specs(self):
        for driver in self.driver_specs:
            self._download_driver_whl(**driver)

    def _download_driver_whl(self, package: str, version: str, source: str = "pypi"):
        """
        Downloads driver from external source, such as pypi, and places
        whl in a local folder for later distribution via API, and local
        install. 
        """
        spec = self._build_spec(package, version)
        print(f"Downloading: {spec}")
        subprocess.run([
            "python", "-m", "pip", "download", spec,
            "--only-binary=:all:",
            "--dest", str(self.driver_dir)
        ], check=True)

        # find downloaded wheel
        pattern = f"{package.replace('-', '_')}*.whl"  # pip använder _ i modulnamn ibland
        whl_files = list(self.driver_dir.glob(pattern))
        if not whl_files:
            raise FileNotFoundError(f"No wheel found for {spec} in {self.driver_dir}")
        
        # install first if many
        whl_path = whl_files[0] 
        print(f"Installing wheel: {whl_path}")

        # Installera
        self._install_whl(whl_path)

    def load_drivers(self):
        """Ladda externa drivrutiner via entry_points."""

        for entry_point in entry_points(group="acex.neds"):
            try:
                klass = entry_point.load()
                instance = klass()
                version = entry_point.dist.version 
                self.drivers[klass.__name__] = {
                    "instance": instance,
                    "version": version,
                    "package_name": entry_point.dist.name
                }
            except Exception as e:
                print(f"Fel vid laddning av {entry_point.name}: {e}")

        print("Installed neds:")
        for d in self.drivers:
            print(f" - {d}")

    def driver_download_path(self, driver_name: str) -> NetworkElementDriver:
        """Returnera sökvägen till .whl-filen för en installerad drivrutin."""
        ned = self.drivers.get(driver_name)
        if ned is None:
            return None

        version = ned.get("version")
        package_name = ned.get('package_name')
        pattern = f"{package_name.replace('-', '_')}-{version}-*.whl"
        matches = list(self.driver_dir.glob(pattern))

        if not matches:
            return None
        return str(matches[0])

    def driver_filename(self, driver_name):
        """ Returnera bara filnamnet på driverns whl """
        full_path = self.driver_download_path(driver_name)
        filename = full_path.split('/')[-1]
        return filename

    def get_driver_info(self, driver_name: str) -> NetworkElementDriver:
        """Hämta en drivrutinsinstans efter namn"""
        ned = self.drivers.get(driver_name)

        if ned is None:
            return None

        filename = self.driver_filename(driver_name)
        ned_instance = ned["instance"]
        response = {
            "name": driver_name,
            "version": ned.get("version"),
            "package_name": ned.get('package_name'),
            "description": type(ned_instance).__doc__,
            "filename": filename
        }

        return response

    def list_drivers(self) -> list[dict]:
        """Returnera en lista över tillgängliga drivrutinsnamn."""
        result = []
        for key, driver_data in self.drivers.items():
                driver = driver_data["instance"]
                kind = type(driver)
                filename = self.driver_filename(key)
                info = {
                    "name": key,
                    "version": driver_data.get("version", "n/a"),
                    "package_name": driver_data.get('package_name'),
                    "description": kind.__doc__ or "n/a",
                    "filename": filename
                }
                result.append(info)
        return result