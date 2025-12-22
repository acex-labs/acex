import importlib
import pkgutil
from typing import Dict, Type
from importlib.metadata import entry_points
from acex.plugins.neds.core import NetworkElementDriver

class NEDManager:
    def __init__(self):

        self.drivers: Dict[str, list[NetworkElementDriver]] = {}
        self.load_internal_drivers()
        self.load_external_drivers()

    def load_internal_drivers(self):
        """Ladda interna drivrutiner från plugins.neds.internal-katalogen."""
        base_path = "acex.plugins.neds.internal"
        for importer, module_name, _ in pkgutil.walk_packages(
            path=importlib.import_module(base_path).__path__,
            prefix=f"{base_path}."
        ):
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    klass = getattr(module, attr_name)
                    if (
                        isinstance(klass, type)
                        and issubclass(klass, NetworkElementDriver)
                        and klass is not NetworkElementDriver
                    ):
                        instance = klass()
                        key = instance.key
                        self.drivers.setdefault(key, []).append(instance)
            except Exception as e:
                print(f"Fel vid laddning av {module_name}: {e}")


    def load_external_drivers(self):
        """Ladda externa drivrutiner via entry_points."""

        for entry_point in entry_points(group="acex.neds"):
            try:
                klass = entry_point.load()
                if issubclass(klass, NetworkElementDriver):
                    instance = klass()
                    key = instance.key
                    self.drivers.setdefault(key, []).append(instance)
            except Exception as e:
                print(f"Fel vid laddning av {entry_point.name}: {e}")

    def get_driver(self, driver_name: str, version: str = None) -> NetworkElementDriver:
        """Hämta en drivrutinsinstans efter namn och ev. version. Om version inte anges, returnera den med högst version."""
        candidates = self.drivers.get(driver_name.lower(), [])
        if not candidates:
            raise ValueError(f"Drivrutinen {driver_name} finns inte")
        if version:
            for driver in candidates:
                driver_version = getattr(type(driver), "version", None)
                if driver_version == version:
                    return driver
            raise ValueError(f"Drivrutinen {driver_name} med version {version} finns inte")
        if len(candidates) == 1:
            return candidates[0]
        try:
            from packaging.version import parse as parse_version
            candidates.sort(key=lambda d: parse_version(getattr(type(d), "version", "0.0.0")), reverse=True)
        except ImportError:
            candidates.sort(key=lambda d: getattr(type(d), "version", "0.0.0"), reverse=True)
        return candidates[0]

    def list_drivers(self) -> list[dict]:
        """Returnera en lista över tillgängliga drivrutinsnamn."""
        result = []
        for key, drivers in self.drivers.items():
            for driver in drivers:
                kind = type(driver)
                info = {
                    "name": getattr(kind, "name", key),
                    "class": kind.__name__,
                    "version": getattr(kind, "version", "n/a"),
                    "description": kind.__doc__ or "n/a",
                    "identifier": driver.key
                }
                result.append(info)
        return result