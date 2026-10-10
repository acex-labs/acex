"""The ztp discover handler uses the NED an administrator chose for the job's ZTP method."""

from __future__ import annotations

import pytest
import respx
from acex_client import Acex
from acex_devkit.models.job import JobResponse
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
