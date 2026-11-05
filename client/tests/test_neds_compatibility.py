"""A process that names the NED interfaces it can run does not install or hand out a driver of another one."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
import respx
from acex_client.auth import NullAuthProvider
from acex_client.exceptions import AcexNedIncompatibleError, AcexNedInstallError
from acex_client.http import RestClient
from acex_client.resources.neds import Neds
from acex_devkit.models.ned import Ned
from httpx import Response

PUBLISHED = {
    "name": "CiscoIOS",
    "package_name": "acex-driver-cisco-ioscli",
    "version": "5.0.0",
    "description": "Cisco IOS",
    "filename": "acex_driver_cisco_ioscli-5.0.0-py3-none-any.whl",
}


def published(**fields) -> dict:
    return {**PUBLISHED, **fields}


@pytest.fixture
def rest():
    r = RestClient("http://test/api/v1", NullAuthProvider(), timeout=5.0)
    try:
        yield r
    finally:
        r.close()


@pytest.fixture
def neds(rest):
    return Neds(rest, ned_interfaces=[2])


def list_on_the_api(*neds_on_the_api: dict) -> None:
    respx.get("http://test/api/v1/neds").mock(return_value=Response(200, json=list(neds_on_the_api)))


@pytest.fixture(autouse=True)
def nothing_installed():
    with patch("acex_client.resources.neds.importlib.metadata.entry_points", return_value=[]):
        yield


@respx.mock
def test_a_driver_of_a_newer_interface_is_not_listed_as_missing(neds):
    list_on_the_api(published(interface_version=3))

    assert neds.get_missing() == []
    assert neds.incompatible == {
        "CiscoIOS": "CiscoIOS v5.0.0 implements NED interface 3, this process runs 2: update this agent or worker"
    }


@respx.mock
def test_a_driver_of_an_older_interface_says_to_update_the_api(neds):
    list_on_the_api(published(interface_version=1))

    assert neds.get_missing() == []
    assert neds.incompatible["CiscoIOS"].endswith("update the API, whose driver is older")


@respx.mock
def test_a_driver_of_a_supported_interface_is_listed_as_before(neds):
    list_on_the_api(published(interface_version=2))

    assert [n.name for n in neds.get_missing()] == ["CiscoIOS"]
    assert neds.incompatible == {}


@respx.mock
def test_a_driver_that_does_not_say_which_interface_counts_as_the_first_one(neds):
    list_on_the_api(published())

    assert neds.get_missing() == []
    assert neds.incompatible["CiscoIOS"].startswith("CiscoIOS v5.0.0 implements NED interface 1")
    assert neds.incompatible["CiscoIOS"].endswith("update the API, whose driver is older")


@respx.mock
def test_a_process_that_also_runs_the_first_interface_gets_a_driver_that_does_not_say(rest):
    list_on_the_api(published())

    assert [n.name for n in Neds(rest, ned_interfaces=[1, 2]).get_missing()] == ["CiscoIOS"]


@respx.mock
def test_a_process_that_names_no_interfaces_gets_every_driver(rest):
    list_on_the_api(published(interface_version=3))

    assert [n.name for n in Neds(rest).get_missing()] == ["CiscoIOS"]


@respx.mock
def test_the_other_drivers_are_still_listed(neds):
    list_on_the_api(
        published(interface_version=3),
        published(name="JunosCLI", package_name="acex-driver-juniper-junoscli", interface_version=2),
    )

    assert [n.name for n in neds.get_missing()] == ["JunosCLI"]
    assert list(neds.incompatible) == ["CiscoIOS"]


@respx.mock
def test_the_reason_is_forgotten_once_the_driver_fits(neds):
    list_on_the_api(published(interface_version=3))
    neds.get_missing()
    assert neds.incompatible

    respx.reset()
    list_on_the_api(published(interface_version=2))

    assert [n.name for n in neds.get_missing()] == ["CiscoIOS"]
    assert neds.incompatible == {}


@respx.mock
def test_the_same_reason_is_logged_once(neds, caplog):
    list_on_the_api(published(interface_version=3))

    with caplog.at_level(logging.WARNING, logger="acex_client.neds"):
        neds.get_missing()
        neds.get_missing()

    assert [r.getMessage() for r in caplog.records].count(f"NED not used: {neds.incompatible['CiscoIOS']}") == 1


@respx.mock
def test_install_refuses_before_anything_is_downloaded(neds):
    ned = Ned(**published(interface_version=3))

    with pytest.raises(AcexNedIncompatibleError, match="implements NED interface 3"):
        neds.install(ned)


def test_a_refusal_is_an_install_error_so_existing_handlers_catch_it():
    assert issubclass(AcexNedIncompatibleError, AcexNedInstallError)


@respx.mock
def test_load_refuses_a_driver_of_another_interface(neds):
    respx.get("http://test/api/v1/neds/CiscoIOS").mock(return_value=Response(200, json=published(interface_version=3)))

    with pytest.raises(AcexNedIncompatibleError, match="update this agent or worker"):
        neds.load("CiscoIOS")

    assert "CiscoIOS" in neds.incompatible


class _FakeDist:
    version = "5.0.0"


class _FakeEntryPoint:
    value = "pkg:CiscoIOS"
    dist = _FakeDist()

    def __init__(self, driver_class):
        self._driver_class = driver_class

    def load(self):
        return self._driver_class


class _DriverOfInterface2:
    interface_version = 2


class _DriverOfInterface3:
    interface_version = 3


class _DriverThatDoesNotSay:
    pass


def installed(driver_class):
    return patch(
        "acex_client.resources.neds.importlib.metadata.entry_points", return_value=[_FakeEntryPoint(driver_class)]
    )


def test_an_installed_driver_of_a_supported_interface_is_handed_out(neds):
    with installed(_DriverOfInterface2):
        assert isinstance(neds.get_driver_instance("CiscoIOS"), _DriverOfInterface2)


def test_an_installed_driver_of_another_interface_is_not_handed_out(neds):
    with installed(_DriverOfInterface3):
        assert neds.get_driver_instance("CiscoIOS") is None

    assert neds.incompatible["CiscoIOS"].startswith("CiscoIOS v5.0.0 implements NED interface 3")


def test_an_installed_driver_that_does_not_say_which_interface_counts_as_the_first_one(neds):
    with installed(_DriverThatDoesNotSay):
        assert neds.get_driver_instance("CiscoIOS") is None

    assert neds.incompatible["CiscoIOS"].startswith("CiscoIOS v5.0.0 implements NED interface 1")


def test_a_process_that_names_no_interfaces_gets_every_installed_driver(rest):
    with installed(_DriverOfInterface3):
        assert isinstance(Neds(rest).get_driver_instance("CiscoIOS"), _DriverOfInterface3)
