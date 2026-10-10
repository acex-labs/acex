from importlib.metadata import entry_points
from pathlib import Path

from acex.plugins.neds.core import NetworkElementDriver

from .wheels import built_wheels


class NEDManager:
    def __init__(self):
        self.drivers: dict[str, list[NetworkElementDriver]] = {}

    def wheel_path(self, filename: str) -> Path | None:
        """The wheel served under `filename`, if it is one the backend built."""
        for path in built_wheels().values():
            if path.name == filename:
                return path
        return None

    def _driver_filename(self, driver_name):
        """Returnera bara filnamnet på driverns whl"""
        ned = self.drivers.get(driver_name)
        if ned is None:
            return None
        path = built_wheels().get(ned["package_name"])
        return path.name if path else None

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
                    "package_name": entry_point.dist.name,
                }
            except Exception as e:
                print(f"Fel vid laddning av {entry_point.name}: {e}")

        print("Installed neds:")
        for d in self.drivers:
            print(f" - {d}")

    def get_driver_instance(self, driver_name: str):
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
            "package_name": ned.get("package_name"),
            "description": type(ned_instance).__doc__,
            "filename": filename,
        }

        return response

    def list_drivers(self) -> list[dict]:
        """Returnera en lista över tillgängliga drivrutinsnamn via entry points."""
        result = []
        for ep in entry_points(group="acex.neds"):
            class_name = ep.value.split(":")[-1]
            try:
                dist = ep.dist
                version = dist.version
                package_name = dist.name
                # Try to get description from cached instance, else load class doc
                cached = self.drivers.get(class_name)
                if cached:
                    description = type(cached["instance"]).__doc__ or "n/a"
                    filename = self._driver_filename(class_name)
                else:
                    klass = ep.load()
                    description = klass.__doc__ or "n/a"
                    filename = None
            except Exception:
                version = "n/a"
                package_name = "n/a"
                description = "n/a"
                filename = None
            result.append(
                {
                    "name": class_name,
                    "version": version,
                    "package_name": package_name,
                    "description": description,
                    "filename": filename,
                }
            )
        return result
