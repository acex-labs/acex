"""The ztp discover handler uses the NED an administrator chose for the job's ZTP method."""

from __future__ import annotations

import pytest
import respx
from acex_client import Acex
from acex_devkit.exceptions import AuthenticationFailed, HostUnreachable, SshAlgorithmMismatch
from acex_devkit.models.job import JobResponse
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.state import DeviceFacts
from acex_worker.handlers import ztp_discover
from acex_worker.handlers.ztp_discover import HandleZtpDiscovery
from httpx import Response

BASE = "http://test"
API = f"{BASE}/api/v1"

JOB = JobResponse.model_validate(
    {
        "id": 7,
        "type": "acex.ztp.discover",
        "data": {"ip": "10.1.2.3", "method": "cisco_iosxe_python"},
        "state": "running",
        "created_by": "system",
        "created_at": "2026-10-09T00:00:00Z",
    }
)


class FakeDriver:
    pass


@pytest.fixture
def client():
    with respx.mock:
        respx.get(f"{API}/auth/config").mock(return_value=Response(200, json={"enabled": False}))
        with Acex(BASE) as client:
            yield client


def chosen(ned: str | None, login: tuple[str, str] | None = ("acex-ztp", "Temp123")) -> None:
    username, password = login or (None, None)
    respx.get(f"{API}/ztp_methods/cisco_iosxe_python").mock(
        return_value=Response(
            200,
            json={
                "method": "cisco_iosxe_python",
                "label": "Cisco IOS XE — Python",
                "description": "",
                "ned": ned,
                "bootstrap_username": username,
                "bootstrap_password": password,
            },
        )
    )


def test_no_ned_chosen_fails_the_job(client):
    chosen(None)

    response = HandleZtpDiscovery().handle_hook(client, JOB)

    assert not response.success
    assert "No NED is chosen for ZTP method cisco_iosxe_python" in response.error


def test_no_bootstrap_login_fails_the_job(client):
    chosen("CiscoIOSCLIDriver", login=None)

    response = HandleZtpDiscovery().handle_hook(client, JOB)

    assert not response.success
    assert "No bootstrap login is set for ZTP method cisco_iosxe_python" in response.error


def published(version: str) -> None:
    respx.get(f"{API}/neds/CiscoIOSCLIDriver").mock(
        return_value=Response(
            200,
            json={
                "name": "CiscoIOSCLIDriver",
                "package_name": "acex-driver-cisco-ioscli",
                "version": version,
                "description": "",
                "filename": f"acex_driver_cisco_ioscli-{version}-py3-none-any.whl",
            },
        )
    )


def test_the_chosen_ned_is_loaded(client, monkeypatch):
    chosen("CiscoIOSCLIDriver")
    published("0.0.2")
    monkeypatch.setattr(client.neds, "installed_version", lambda name: "0.0.2")
    asked = []
    monkeypatch.setattr(client.neds, "get_driver_instance", lambda name: asked.append(name) or FakeDriver())

    HandleZtpDiscovery().handle_hook(client, JOB)

    assert asked == ["CiscoIOSCLIDriver"]


def test_a_chosen_ned_that_is_not_installed_is_installed_first(client, monkeypatch):
    chosen("CiscoIOSCLIDriver")
    published("0.0.2")
    installed = []
    monkeypatch.setattr(client.neds, "installed_version", lambda name: "0.0.2" if installed else None)
    monkeypatch.setattr(client.neds, "install", lambda ned: installed.append(ned.name) or True)
    monkeypatch.setattr(client.neds, "get_driver_instance", lambda name: FakeDriver())

    HandleZtpDiscovery().handle_hook(client, JOB)

    assert installed == ["CiscoIOSCLIDriver"]


FACTS = DeviceFacts(
    vendor=Vendor.cisco,
    os=OS.cisco_iosxe,
    os_version="17.9.4a",
    hardware_model="C9300-24P",
    serial_number="FOC2345L0AB",
)


class FakeSession:
    def __init__(self, driver: DiscoveringDriver):
        self.driver = driver

    async def __aenter__(self) -> FakeSession:
        if self.driver.errors:
            raise self.driver.errors.pop(0)
        return self

    async def __aexit__(self, *exc) -> None:
        pass

    async def get_facts(self) -> DeviceFacts:
        return self.driver.facts


class DiscoveringDriver:
    """A NED whose device answers with `facts` once the `errors` are used up."""

    def __init__(self, facts: DeviceFacts = FACTS, errors: list[Exception] = ()):
        self.facts = facts
        self.errors = list(errors)
        self.connected = []

    def connect(self, address, credentials, node=None):
        self.connected.append((address, [c.fields for c in credentials], node))
        return FakeSession(self)


@pytest.fixture
def device(client, monkeypatch):
    chosen("CiscoIOSCLIDriver")
    driver = DiscoveringDriver()
    monkeypatch.setattr(ztp_discover, "load_ned", lambda client, name: driver)
    return driver


def handler(waited: list[int], *, seconds_per_look: int = 1) -> HandleZtpDiscovery:
    """A handler that notes its pauses instead of sleeping them, and whose clock moves with every look."""
    handler = HandleZtpDiscovery()
    clock = iter(range(0, 10_000, seconds_per_look))
    handler.sleep = waited.append
    handler.clock = lambda: next(clock)
    return handler


def test_discovery_reports_what_the_device_says_it_is(client, device):
    response = HandleZtpDiscovery().handle_hook(client, JOB)

    assert response.success, response.error
    assert response.result == {
        "serial_number": "FOC2345L0AB",
        "vendor": "cisco",
        "hardware_model": "C9300-24P",
        "os": "cisco_iosxe",
        "os_version": "17.9.4a",
    }


def test_the_device_is_reached_at_its_address_with_the_bootstrap_login_and_without_a_node(client, device):
    HandleZtpDiscovery().handle_hook(client, JOB)

    assert device.connected == [("10.1.2.3", [{"username": "acex-ztp", "password": "Temp123"}], None)]


def test_a_device_that_does_not_answer_yet_is_tried_again(client, device):
    device.errors = [HostUnreachable("refused"), AuthenticationFailed("no such login yet")]
    waited = []

    response = handler(waited).handle_hook(client, JOB)

    assert response.success, response.error
    assert waited == [5, 10]
    assert len(device.connected) == 3


def test_a_device_that_never_answers_fails_the_job_after_the_patience(client, device):
    device.errors = [HostUnreachable("refused")] * 100
    waited = []

    response = handler(waited, seconds_per_look=100).handle_hook(client, JOB)

    assert not response.success
    assert "10.1.2.3 did not take the bootstrap login in 600 seconds" in response.error
    assert "refused" in response.error
    assert len(waited) < 10


def test_a_failure_that_waiting_does_not_cure_fails_the_job_at_once(client, device):
    device.errors = [SshAlgorithmMismatch("no algorithm in common")]
    waited = []

    response = handler(waited).handle_hook(client, JOB)

    assert not response.success
    assert "no algorithm in common" in response.error
    assert waited == []


def test_a_device_that_reports_no_serial_number_fails_the_job(client, device):
    device.facts = FACTS.model_copy(update={"serial_number": None})

    response = HandleZtpDiscovery().handle_hook(client, JOB)

    assert not response.success
    assert "10.1.2.3 did not report a serial number" in response.error
