import importlib
import pkgutil
from typing import Dict, Type
from importlib.metadata import entry_points
from acex.constants import NED_WHEEL_DIR#, DEFAULT_DRIVERS
from acex.plugins.neds.core import NetworkElementDriver
from acex.models.ned import Ned

import os
import subprocess
import sys
from pathlib import Path
import zipfile


class NEDManager:
    def __init__(self):

        self.driver_dir = Path.cwd() / NED_WHEEL_DIR # TODO: Fix a more robust way to discover project root. or just be run at specifik cli command
        self.driver_dir.mkdir(parents=True, exist_ok=True)
        self.drivers: Dict[str, list[NetworkElementDriver]] = {}

        self._build_wheels()

    def _driver_download_path(self, driver_name: str) -> NetworkElementDriver:
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

    def _driver_filename(self, driver_name):
        """ Returnera bara filnamnet på driverns whl """
        full_path = self._driver_download_path(driver_name)
        filename = full_path.split('/')[-1]
        return filename

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

    def _build_wheels(self):
        """
        Build wheels for all installed drivers and store in distribution folder
        for client downloads.

        Builds wheels for all installed drivers based on entry point "acex.neds",
        creates a new zipped whl and places in the dist-dir for wheels to be 
        served via the API. 
        """
        whl_dir = self.driver_dir
        for ep in entry_points(group="acex.neds"):
            dist = ep.dist
            name = dist.metadata["Name"].replace("-", "_")
            version = dist.version
            tag = "py3-none-any"
            wheel_name = f"{name}-{version}-{tag}.whl"
            wheel_path = Path(whl_dir) / wheel_name

            if os.path.exists(wheel_path):
                ...
            else:
                with zipfile.ZipFile(wheel_path, "w") as z:
                    root = dist.locate_file("")
                    # Lägg till alla paketfiler
                    for file in dist.files:
                        src = root / file
                        if src.is_file():
                            print(file)
                            z.write(src, file)
                    # Lägg till .dist-info-mappen och dess innehåll
                    dist_info_dirs = [f for f in dist.files if f.parts[-1].endswith('.dist-info')]
                    for dist_info in dist_info_dirs:
                        dist_info_path = root / dist_info
                        if dist_info_path.is_dir():
                            for dirpath, dirnames, filenames in os.walk(dist_info_path):
                                for filename in filenames:
                                    file_path = Path(dirpath) / filename
                                    arcname = file_path.relative_to(root)
                                    z.write(file_path, arcname)

    def get_driver_instance(self, driver_name:str):
        """
        Returns an instance of the driver class based on name.
        Checks for installed driver based on entrypoint and then name
        of the class. 
        """
        for entry_point in entry_points(group="acex.neds"):
            if entry_point.value.split(":")[-1] == driver_name:
                return entry_point.load()()

    def get_driver_info(self, driver_name: str) -> NetworkElementDriver:
        """Hämta en drivrutinsinstans efter namn"""
        ned = self.drivers.get(driver_name)

        if ned is None:
            return None

        filename = self._driver_filename(driver_name)
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
                filename = self._driver_filename(key)
                info = {
                    "name": key,
                    "version": driver_data.get("version", "n/a"),
                    "package_name": driver_data.get('package_name'),
                    "description": kind.__doc__ or "n/a",
                    "filename": filename
                }
                result.append(info)
        return result