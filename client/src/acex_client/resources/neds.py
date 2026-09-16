from __future__ import annotations

import importlib
import importlib.metadata
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from acex_devkit.models.ned import Ned

from acex_client.exceptions import AcexNedInstallError
from acex_client.resources.base import (
    ActionMixin,
    Resource,
    action,
)

logger = logging.getLogger("acex_client.neds")

_ENTRY_POINT_GROUP = "acex.neds"


def _top_level_modules(package_name: str) -> set[str]:
    """Return the top-level import names provided by an installed distribution."""
    try:
        dist = importlib.metadata.distribution(package_name)
    except importlib.metadata.PackageNotFoundError:
        return set()

    top_level = dist.read_text("top_level.txt")
    if top_level:
        return {line.strip() for line in top_level.splitlines() if line.strip()}
    return {f.parts[0] for f in (dist.files or []) if len(f.parts) > 1 and f.suffix == ".py"}


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

    def install(self, ned: Ned) -> bool:
        """Download a NED wheel from the backend and pip-install it into the
        current environment.

        Returns True when the driver is usable in this process straight away,
        and False when the package was already imported at an older version —
        pip replaces the files on disk, but the interpreter keeps serving the
        module it already loaded, so that case needs an agent restart.

        Raises AcexNedInstallError if pip fails or the installed distribution
        does not show up afterwards.
        """
        wheel_bytes = self.download(filename=ned.filename)

        # Installing an upgrade over an already-imported package cannot take
        # effect in this process, so find that out before pip moves the files.
        stale_modules = _top_level_modules(ned.package_name) & sys.modules.keys()

        with tempfile.TemporaryDirectory(prefix="acex-ned-") as tmpdir:
            wheel = Path(tmpdir) / ned.filename
            wheel.write_bytes(wheel_bytes)
            # --upgrade (rather than --force-reinstall) installs exactly this
            # wheel, including downgrades, but leaves satisfied dependencies
            # alone instead of re-resolving the whole tree against PyPI.
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--no-input",
                    "--disable-pip-version-check",
                    "--no-warn-script-location",
                    str(wheel),
                ],
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip().splitlines()
            raise AcexNedInstallError(
                f"pip install of {ned.filename} failed (exit {result.returncode}): " + " | ".join(output[-5:])
            )

        pip_summary = (result.stdout or "").strip().splitlines()
        logger.debug("pip install %s: %s", ned.filename, pip_summary[-1] if pip_summary else "no output")

        # pip wrote into site-packages behind the interpreter's back; drop the
        # cached directory listings so the new distribution is discoverable.
        importlib.invalidate_caches()

        installed = _local_drivers().get(ned.name)
        if installed is None:
            raise AcexNedInstallError(
                f"{ned.package_name} {ned.version} installed, but no '{_ENTRY_POINT_GROUP}' "
                f"entry point named '{ned.name}' was found afterwards"
            )
        if installed["version"] != ned.version:
            raise AcexNedInstallError(
                f"{ned.package_name} reports version {installed['version']} after installing {ned.version}"
            )

        return not stale_modules

    def get_driver_instance(self, ned_id: str):
        """Return an instantiated NED driver class by its class name.

        Looks up locally installed NEDs via the `acex.neds` entry-point group.
        Returns None if the driver is not installed.
        """
        for ep in importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP):
            if ep.value.split(":")[-1] == ned_id:
                return ep.load()()
        return None
