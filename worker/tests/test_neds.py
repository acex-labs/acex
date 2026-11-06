"""The worker keeps its NEDs at the versions the backend publishes."""

from __future__ import annotations

import logging

import pytest
from acex_client.exceptions import AcexNedIncompatibleError, AcexNedInstallError
from acex_devkit.drivers import NED_INTERFACE
from acex_devkit.models.ned import Ned
from acex_worker import neds
from acex_worker.neds import SUPPORTED_NED_INTERFACES, NedUnavailable, load_ned, sync_neds


def ned(version: str) -> Ned:
    return Ned(
        name="CiscoIOSCLIDriver",
        package_name="acex-driver-cisco-ioscli",
        version=version,
        description="",
        filename=f"acex_driver_cisco_ioscli-{version}-py3-none-any.whl",
    )


class FakeDriver:
    pass


class FakeNeds:
    """Stands in for client.neds: a backend publishing `published`, with `local` installed here."""

    def __init__(self, published: str, local: str | None, usable: bool = True):
        self.published = published
        self.local = local
        self.usable = usable
        self.installed: list[str] = []
        self.incompatible: dict[str, str] = {}

    def get(self, ned_id: str) -> Ned:
        return ned(self.published)

    def get_missing(self) -> list[Ned]:
        return [] if self.local == self.published else [ned(self.published)]

    def installed_version(self, ned_id: str) -> str | None:
        return self.local

    def install(self, n: Ned) -> bool:
        self.installed.append(n.version)
        self.local = n.version
        return self.usable

    def get_driver_instance(self, ned_id: str):
        return FakeDriver() if self.local else None


class FakeClient:
    def __init__(self, fake_neds: FakeNeds):
        self.neds = fake_neds


@pytest.fixture(autouse=True)
def restarts(monkeypatch):
    requested = []
    monkeypatch.setattr(neds, "_request_restart", lambda: requested.append(True))
    monkeypatch.setattr(neds, "_stale", set())
    return requested


def test_sync_installs_missing_neds():
    client = FakeClient(FakeNeds(published="0.0.2", local=None))

    sync_neds(client)

    assert client.neds.installed == ["0.0.2"]


def test_sync_skips_a_ned_that_fails_to_install():
    fake = FakeNeds(published="0.0.2", local=None)

    def broken(n):
        raise AcexNedInstallError("pip failed")

    fake.install = broken

    sync_neds(FakeClient(fake))


def test_load_uses_an_up_to_date_ned_without_installing():
    client = FakeClient(FakeNeds(published="0.0.2", local="0.0.2"))

    assert isinstance(load_ned(client, "CiscoIOSCLIDriver"), FakeDriver)
    assert client.neds.installed == []


def test_load_upgrades_an_outdated_ned():
    client = FakeClient(FakeNeds(published="0.0.3", local="0.0.2"))

    assert isinstance(load_ned(client, "CiscoIOSCLIDriver"), FakeDriver)
    assert client.neds.installed == ["0.0.3"]


def test_an_upgrade_over_an_imported_ned_restarts_the_worker(restarts):
    client = FakeClient(FakeNeds(published="0.0.3", local="0.0.2", usable=False))

    with pytest.raises(NedUnavailable, match="restarting"):
        load_ned(client, "CiscoIOSCLIDriver")
    assert restarts == [True]

    # Later jobs must not run the old code still in memory, though the disk is up to date.
    with pytest.raises(NedUnavailable, match="restarting"):
        load_ned(client, "CiscoIOSCLIDriver")
    assert client.neds.installed == ["0.0.3"]


def test_a_job_learns_why_a_driver_of_another_interface_was_not_installed():
    fake = FakeNeds(published="0.0.3", local="0.0.2")

    def refused(n):
        raise AcexNedIncompatibleError(f"{n.name} v{n.version} implements NED interface 3: update this agent or worker")

    fake.install = refused

    with pytest.raises(NedUnavailable, match="v0.0.3 could not be installed: .*update this agent or worker"):
        load_ned(FakeClient(fake), "CiscoIOSCLIDriver")


def test_a_job_learns_why_an_installed_driver_is_not_handed_out():
    fake = FakeNeds(published="0.0.2", local="0.0.2")
    fake.get_driver_instance = lambda ned_id: None
    fake.incompatible["CiscoIOSCLIDriver"] = "implements NED interface 3: update this agent or worker"

    with pytest.raises(NedUnavailable, match="cannot be used: implements NED interface 3"):
        load_ned(FakeClient(fake), "CiscoIOSCLIDriver")


def test_the_worker_runs_the_interface_devkit_defines():
    assert NED_INTERFACE in SUPPORTED_NED_INTERFACES, (
        f"devkit defines NED interface {NED_INTERFACE}: make the worker run it and add it to "
        "SUPPORTED_NED_INTERFACES, otherwise workers install no driver"
    )


def test_sync_says_everything_is_up_to_date_when_no_driver_was_left_out(caplog):
    client = FakeClient(FakeNeds(published="0.0.2", local="0.0.2"))

    with caplog.at_level(logging.INFO, logger="acex_worker"):
        sync_neds(client)

    assert [r.getMessage() for r in caplog.records] == ["All NEDs are installed and up to date"]


def test_sync_does_not_say_everything_is_up_to_date_when_a_driver_was_left_out(caplog):
    client = FakeClient(FakeNeds(published="0.0.2", local="0.0.2"))
    client.neds.incompatible["CiscoIOSCLIDriver"] = "implements NED interface 3: update this agent or worker"

    with caplog.at_level(logging.INFO, logger="acex_worker"):
        sync_neds(client)

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "No NED to install; not used by this worker: CiscoIOSCLIDriver"


def test_a_job_learns_why_an_installed_driver_could_not_be_loaded():
    fake = FakeNeds(published="0.0.2", local="0.0.2")
    fake.get_driver_instance = lambda ned_id: None
    fake.incompatible["CiscoIOSCLIDriver"] = "CiscoIOSCLIDriver v0.0.2 could not be loaded: ImportError: no netmiko"

    with pytest.raises(NedUnavailable, match="cannot be used: .*could not be loaded: ImportError: no netmiko"):
        load_ned(FakeClient(fake), "CiscoIOSCLIDriver")


def test_a_job_is_told_when_a_driver_is_missing_and_nothing_says_why():
    fake = FakeNeds(published="0.0.2", local="0.0.2")
    fake.get_driver_instance = lambda ned_id: None

    with pytest.raises(NedUnavailable, match="was installed but its driver class could not be loaded"):
        load_ned(FakeClient(fake), "CiscoIOSCLIDriver")
