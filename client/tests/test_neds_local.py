"""Unit tests for Neds local-driver operations: get_missing, install, get_driver_instance.

These tests exercise the logic that runs on top of the HTTP layer —
get_missing compares remote list against locally installed entry-points,
install downloads a wheel and pip-installs it, and get_driver_instance
resolves an installed driver via importlib.metadata.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.http import RestClient
from acex_client.resources.neds import Neds
from acex_devkit.models.ned import Ned
from httpx import Response


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@pytest.fixture
def neds(rest):
    return Neds(rest)


# ---------------------------------------------------------------------------
# get_missing
# ---------------------------------------------------------------------------


# A fake entry-point dist that mimics what importlib.metadata.entry_points returns.
class _FakeDist:
    def __init__(self, name, version):
        self.name = name
        self.version = version


class _FakeEntryPoint:
    def __init__(self, name, dist, value, load_fn=None):
        self.name = name
        self.dist = dist
        self.value = value
        self._load_fn = load_fn or (lambda: None)

    def load(self):
        return self._load_fn()


def _make_eps(installed):
    """Build a fake entry-points list. `installed` is a dict of {class_name: {package_name, version}}."""
    eps = []
    for class_name, info in installed.items():
        dist = _FakeDist(info["package_name"], info["version"])
        eps.append(_FakeEntryPoint(name=class_name, dist=dist, value=f"pkg:{class_name}"))
    return eps


@respx.mock
@patch("acex_client.resources.neds.importlib.metadata.entry_points")
def test_get_missing_returns_neds_not_installed_locally(mock_eps, neds):
    mock_eps.return_value = _make_eps({})
    respx.get("http://test/api/v1/neds").mock(
        return_value=Response(
            200,
            json=[
                {
                    "name": "CiscoIOS",
                    "package_name": "acex-driver-cisco-ioscli",
                    "version": "1.0.0",
                    "description": "Cisco IOS",
                    "filename": "acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
                },
                {
                    "name": "JunosCLI",
                    "package_name": "acex-driver-juniper-junoscli",
                    "version": "2.0.0",
                    "description": "Juniper Junos",
                    "filename": "acex_driver_juniper_junoscli-2.0.0-py3-none-any.whl",
                },
            ],
        )
    )
    missing = neds.get_missing()
    assert len(missing) == 2
    assert {m.name for m in missing} == {"CiscoIOS", "JunosCLI"}


@respx.mock
@patch("acex_client.resources.neds.importlib.metadata.entry_points")
def test_get_missing_returns_neds_with_version_mismatch(mock_eps, neds):
    mock_eps.return_value = _make_eps({"CiscoIOS": {"package_name": "acex-driver-cisco-ioscli", "version": "0.9.0"}})
    respx.get("http://test/api/v1/neds").mock(
        return_value=Response(
            200,
            json=[
                {
                    "name": "CiscoIOS",
                    "package_name": "acex-driver-cisco-ioscli",
                    "version": "1.0.0",
                    "description": "Cisco IOS",
                    "filename": "acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
                },
            ],
        )
    )
    missing = neds.get_missing()
    assert len(missing) == 1
    assert missing[0].name == "CiscoIOS"
    assert missing[0].version == "1.0.0"


@respx.mock
@patch("acex_client.resources.neds.importlib.metadata.entry_points")
def test_get_missing_returns_empty_when_all_up_to_date(mock_eps, neds):
    mock_eps.return_value = _make_eps({"CiscoIOS": {"package_name": "acex-driver-cisco-ioscli", "version": "1.0.0"}})
    respx.get("http://test/api/v1/neds").mock(
        return_value=Response(
            200,
            json=[
                {
                    "name": "CiscoIOS",
                    "package_name": "acex-driver-cisco-ioscli",
                    "version": "1.0.0",
                    "description": "Cisco IOS",
                    "filename": "acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
                },
            ],
        )
    )
    missing = neds.get_missing()
    assert missing == []


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@respx.mock
@patch("acex_client.resources.neds.subprocess.check_call")
@patch("acex_client.resources.neds.Path.write_bytes")
def test_install_downloads_wheel_and_calls_pip(mock_write, mock_pip, neds):
    respx.get("http://test/api/v1/neds/download/acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl").mock(
        return_value=Response(200, content=b"wheel bytes")
    )
    ned = Ned(
        name="CiscoIOS",
        package_name="acex-driver-cisco-ioscli",
        version="1.0.0",
        description="Cisco IOS",
        filename="acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
    )
    neds.install(ned)
    assert mock_write.called
    mock_pip.assert_called_once()
    pip_args = mock_pip.call_args[0][0]
    assert "pip" in pip_args
    assert "install" in pip_args


# ---------------------------------------------------------------------------
# get_driver_instance
# ---------------------------------------------------------------------------


@patch("acex_client.resources.neds.importlib.metadata.entry_points")
def test_get_driver_instance_returns_loaded_class(mock_eps, neds):
    class _FakeDriver:
        pass

    def _load():
        return _FakeDriver

    dist = _FakeDist("acex-driver-cisco-ioscli", "1.0.0")
    mock_eps.return_value = [_FakeEntryPoint(name="CiscoIOS", dist=dist, value="pkg:CiscoIOS", load_fn=_load)]
    driver = neds.get_driver_instance("CiscoIOS")
    assert isinstance(driver, _FakeDriver)


@patch("acex_client.resources.neds.importlib.metadata.entry_points")
def test_get_driver_instance_returns_none_for_uninstalled(mock_eps, neds):
    mock_eps.return_value = _make_eps({"CiscoIOS": {"package_name": "acex-driver-cisco-ioscli", "version": "1.0.0"}})
    driver = neds.get_driver_instance("Nonexistent")
    assert driver is None
