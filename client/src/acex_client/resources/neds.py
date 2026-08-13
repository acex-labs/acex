from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from pathlib import Path

from acex_devkit.models.ned import Ned

from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)

_ENTRY_POINT_GROUP = "acex.neds"


def _local_drivers() -> dict[str, dict]:
    """Return locally installed NEDs keyed by class name -> {package_name, version, entry_point}."""
    result: dict[str, dict] = {}
    for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
        class_name = ep.value.split(":")[-1]
        result[class_name] = {
            "package_name": ep.dist.name,
            "version": ep.dist.version,
            "entry_point": ep,
        }
    return result


class Neds(Resource, ActionMixin):
    """NED (Network Element Driver) metadata and downloads — `/neds/*`.

    Also exposes local-driver operations (`get_missing`, `install`,
    `get_driver_instance`) used by the collection agent to sync and load drivers.
    """

    path = "/neds"
    response_model = Ned  # type: ignore
    list_model = Ned  # type: ignore
    create_model = None  # type: ignore
    update_model = None  # type: ignore

    @action("GET", "")
    def query(self) -> list[Ned]: ...

    @action("GET", "{ned_id}")
    def get(self, ned_id: str) -> Ned: ...

    def download(self, filename: str) -> bytes:
        """Download a NED wheel as raw bytes."""
        return self.rest.download(f"{self.path}/download/{filename}")

    def get_missing(self) -> list[Ned]:
        """Return NEDs available on the backend but not installed locally
        (or installed at a different version)."""
        remote = self.query()
        local = _local_drivers()
        missing: list[Ned] = []
        for ned in remote:
            installed = local.get(ned.name)
            if installed is None or installed["version"] != ned.version:
                missing.append(ned)
        return missing

    def install(self, ned: Ned) -> None:
        """Download a NED wheel from the backend and pip-install it into the
        current environment."""
        wheel_bytes = self.download(filename=ned.filename)
        target = Path.cwd() / ned.filename
        target.write_bytes(wheel_bytes)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--force-reinstall", str(target)])

    def get_driver_instance(self, ned_id: str):
        """Return an instantiated NED driver class by its class name.

        Looks up locally installed NEDs via the `acex.neds` entry-point group.
        Returns None if the driver is not installed.
        """
        for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
            if ep.value.split(":")[-1] == ned_id:
                return ep.load()()
        return None
