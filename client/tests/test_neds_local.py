"""Unit tests for Neds local-driver operations: get_missing, install, get_driver_instance.

These tests exercise the logic that runs on top of the HTTP layer —
get_missing compares remote list against locally installed entry-points,
install downloads a wheel and pip-installs it, and get_driver_instance
resolves an installed driver via importlib.metadata.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.exceptions import AcexNedInstallError
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


CISCO_NED = Ned(
    name="CiscoIOS",
    package_name="acex-driver-cisco-ioscli",
    version="1.0.0",
    description="Cisco IOS",
    filename="acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl",
)


def _mock_download():
    respx.get("http://test/api/v1/neds/download/acex_driver_cisco_ioscli-1.0.0-py3-none-any.whl").mock(
        return_value=Response(200, content=b"wheel bytes")
    )


def _pip_result(returncode=0, stdout="Successfully installed acex-driver-cisco-ioscli-1.0.0", stderr=""):
    return subprocess.CompletedProcess(args=["pip"], returncode=returncode, stdout=stdout, stderr=stderr)


@respx.mock
@patch("acex_client.resources.neds.importlib.invalidate_caches")
@patch("acex_client.resources.neds.importlib.metadata.entry_points")
@patch("acex_client.resources.neds._top_level_modules", return_value=set())
@patch("acex_client.resources.neds.subprocess.run")
def test_install_downloads_wheel_and_calls_pip(mock_pip, mock_top_level, mock_eps, mock_invalidate, neds):
    mock_pip.return_value = _pip_result()
    mock_eps.return_value = _make_eps({"CiscoIOS": {"package_name": "acex-driver-cisco-ioscli", "version": "1.0.0"}})
    _mock_download()

    assert neds.install(CISCO_NED) is True

    mock_pip.assert_called_once()
    pip_args = mock_pip.call_args[0][0]
    assert "pip" in pip_args
    assert "install" in pip_args
    # --upgrade installs exactly the given wheel without re-resolving the whole
    # dependency tree, which is what --force-reinstall used to do.
    assert "--upgrade" in pip_args
    assert "--force-reinstall" not in pip_args
    assert pip_args[-1].endswith(CISCO_NED.filename)
    # The new distribution is only discoverable after import caches are dropped.
    assert mock_invalidate.called


@respx.mock
@patch("acex_client.resources.neds.importlib.invalidate_caches")
@patch("acex_client.resources.neds.importlib.metadata.entry_points")
@patch("acex_client.resources.neds._top_level_modules", return_value={"acex_driver_cisco_ioscli"})
@patch("acex_client.resources.neds.subprocess.run")
def test_install_reports_not_usable_when_package_already_imported(
    mock_pip, mock_top_level, mock_eps, mock_invalidate, neds
):
    mock_pip.return_value = _pip_result()
    mock_eps.return_value = _make_eps({"CiscoIOS": {"package_name": "acex-driver-cisco-ioscli", "version": "1.0.0"}})
    _mock_download()

    with patch.dict("sys.modules", {"acex_driver_cisco_ioscli": object()}):
        assert neds.install(CISCO_NED) is False


@respx.mock
@patch("acex_client.resources.neds._top_level_modules", return_value=set())
@patch("acex_client.resources.neds.subprocess.run")
def test_install_raises_with_pip_output_when_pip_fails(mock_pip, mock_top_level, neds):
    mock_pip.return_value = _pip_result(returncode=1, stdout="", stderr="ERROR: conflicting dependencies")
    _mock_download()

    with pytest.raises(AcexNedInstallError, match="conflicting dependencies"):
        neds.install(CISCO_NED)


@respx.mock
@patch("acex_client.resources.neds.importlib.invalidate_caches")
@patch("acex_client.resources.neds.importlib.metadata.entry_points")
@patch("acex_client.resources.neds._top_level_modules", return_value=set())
def test_install_raises_when_entry_point_missing_afterwards(mock_top_level, mock_eps, mock_invalidate, neds):
    mock_eps.return_value = _make_eps({})
    _mock_download()

    with patch("acex_client.resources.neds.subprocess.run", return_value=_pip_result()):
        with pytest.raises(AcexNedInstallError, match="entry point"):
            neds.install(CISCO_NED)


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
