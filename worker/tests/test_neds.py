"""The worker keeps its NEDs at the versions the backend publishes."""

from __future__ import annotations

import pytest
from acex_client.exceptions import AcexNedInstallError
from acex_devkit.models.ned import Ned
from acex_worker import neds
from acex_worker.neds import NedUnavailable, load_ned, sync_neds


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
