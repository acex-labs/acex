"""Keeping the worker's NEDs at the versions the backend publishes, and loading the one a job needs."""

from __future__ import annotations

import logging
import os
import signal
import threading

from acex_client import Acex
from acex_client.exceptions import AcexNedInstallError
from acex_devkit.models.ned import Ned

log = logging.getLogger("acex_worker")

# Jobs run in threads; two of them must not pip install into the same environment at once.
_install_lock = threading.Lock()

# NEDs upgraded on disk after this process imported them. The interpreter keeps
# the old modules, so these must not run again until the worker has restarted.
_stale: set[str] = set()


class NedUnavailable(RuntimeError):
    """The NED could not be installed or loaded."""


def sync_neds(client: Acex) -> None:
    """Install every NED the backend has that is missing here or at another version.

    Run at startup, before any NED is imported, so upgrades take effect. A NED
    that fails to install is logged and skipped: jobs that need it will try again.
    """
    missing = client.neds.get_missing()
    if not missing:
        log.info("All NEDs are installed and up to date")
        return
    for ned in missing:
        try:
            _install(client, ned)
        except NedUnavailable as exc:
            log.error(f"{exc}")


def load_ned(client: Acex, name: str):
    """An instance of the NED named `name`, at the version the backend publishes.

    Installs the NED if it is missing or at another version. If an older version
    was already imported in this process, the worker shuts down so it can be
    restarted on the new code, and the job fails.
    """
    ned = client.neds.get(ned_id=name)

    if client.neds.installed_version(name) != ned.version:
        with _install_lock:
            # Another job may have installed it while this one waited.
            if client.neds.installed_version(name) != ned.version:
                _install(client, ned)

    if name in _stale:
        raise NedUnavailable(f"NED {name} was upgraded to v{ned.version}; the worker is restarting to load it")

    driver = client.neds.get_driver_instance(name)
    if driver is None:
        raise NedUnavailable(f"NED {name} was installed but its driver class could not be loaded")
    return driver


def _install(client: Acex, ned: Ned) -> None:
    log.info(f"Installing NED {ned.name} ({ned.package_name}) v{ned.version}")
    try:
        usable = client.neds.install(ned)
    except AcexNedInstallError as exc:
        raise NedUnavailable(f"NED {ned.name} v{ned.version} could not be installed: {exc}") from exc
    if not usable:
        log.warning(
            f"NED {ned.name} v{ned.version} installed, but {ned.package_name} is already "
            "imported in this process — restarting the worker to run the new code"
        )
        _stale.add(ned.name)
        _request_restart()


def _request_restart() -> None:
    # SIGTERM is Celery's warm shutdown: running jobs finish, no new ones start,
    # and the orchestrator starts a fresh worker.
    os.kill(os.getpid(), signal.SIGTERM)
