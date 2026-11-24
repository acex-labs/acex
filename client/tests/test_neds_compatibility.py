"""A process that names the NED interfaces it can run does not install or hand out a driver of another one."""

from __future__ import annotations

import logging
from types import SimpleNamespace
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


def reason(interface: int, runs: str, remedy: str, version: str = "5.0.0") -> str:
    return f"CiscoIOS v{version} implements NED interface {interface}, this process runs {runs}: {remedy}"


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


def describe_on_the_api(ned: dict) -> None:
    respx.get(f"http://test/api/v1/neds/{ned['name']}").mock(return_value=Response(200, json=ned))


class _FakeDist:
    name = "acex-driver-cisco-ioscli"

    def __init__(self, version):
        self.version = version


class _FakeEntryPoint:
    value = "pkg:CiscoIOS"

    def __init__(self, driver_class, version="5.0.0"):
        self._driver_class = driver_class
        self.dist = _FakeDist(version)

    def load(self):
        if isinstance(self._driver_class, Exception):
            raise self._driver_class
        return self._driver_class


def installed(driver_class, version="5.0.0"):
    return patch(
        "acex_client.resources.neds.importlib.metadata.entry_points",
        return_value=[_FakeEntryPoint(driver_class, version)],
    )


@pytest.fixture(autouse=True)
def nothing_installed():
    with patch("acex_client.resources.neds.importlib.metadata.entry_points", return_value=[]):
        yield


class _DriverOfInterface2:
    interface_version = 2


class _DriverOfInterface3:
    interface_version = 3


class _DriverThatDoesNotSay:
    pass


class _DriverWithAProperty:
    @property
    def interface_version(self):
        return 3


class _DriverThatCannotBeBuilt:
    interface_version = 2

    def __init__(self):
        raise RuntimeError("no transport")


@respx.mock
def test_a_driver_of_a_newer_interface_is_not_listed_as_missing(neds):
    list_on_the_api(published(interface_version=3))

    assert neds.get_missing() == []
    assert neds.incompatible == {"CiscoIOS": reason(3, "2", "update this agent or worker")}


@respx.mock
def test_a_driver_of_an_older_interface_says_to_update_the_api(neds):
    list_on_the_api(published(interface_version=1))

    assert neds.get_missing() == []
    assert neds.incompatible == {"CiscoIOS": reason(1, "2", "update the API, whose driver is older")}


@respx.mock
def test_a_driver_of_a_supported_interface_is_listed_as_before(neds):
    list_on_the_api(published(interface_version=2))

    assert [n.name for n in neds.get_missing()] == ["CiscoIOS"]
    assert neds.incompatible == {}


@respx.mock
def test_a_driver_that_does_not_say_which_interface_is_listed_as_before(neds):
    list_on_the_api(published())

    assert [n.name for n in neds.get_missing()] == ["CiscoIOS"]
    assert neds.incompatible == {}


def test_a_listing_from_an_older_devkit_that_has_no_such_field_is_not_held_against_the_driver(neds):
    ned_without_the_field = SimpleNamespace(name="CiscoIOS", version="5.0.0")

    assert neds.refusal(ned_without_the_field) is None


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
def test_a_process_that_runs_two_interfaces_gets_a_driver_of_either(rest):
    neds = Neds(rest, ned_interfaces=[2, 3])
    list_on_the_api(
        published(name="Two", interface_version=2),
        published(name="Three", interface_version=3),
        published(name="One", interface_version=1),
        published(name="Four", interface_version=4),
    )

    assert [n.name for n in neds.get_missing()] == ["Two", "Three"]
    assert neds.incompatible == {
        "One": "One v5.0.0 implements NED interface 1, this process runs 2, 3: update the API, whose driver is older",
        "Four": "Four v5.0.0 implements NED interface 4, this process runs 2, 3: update this agent or worker",
    }


@respx.mock
def test_a_driver_between_two_interfaces_a_process_runs_blames_neither_side(rest):
    list_on_the_api(published(interface_version=2))

    assert Neds(rest, ned_interfaces=[1, 3]).get_missing() == []


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
def test_the_reason_is_forgotten_once_the_api_no_longer_lists_the_driver(neds):
    list_on_the_api(published(interface_version=3))
    neds.get_missing()

    respx.reset()
    list_on_the_api()

    assert neds.get_missing() == []
    assert neds.incompatible == {}


@pytest.mark.parametrize("ned_interfaces", ["2", b"2", [2, "3"], [2.0], [True], 2, [None]])
def test_ned_interfaces_must_be_a_collection_of_whole_numbers(rest, ned_interfaces):
    with pytest.raises(TypeError, match="ned_interfaces must be a collection of numbers"):
        Neds(rest, ned_interfaces=ned_interfaces)


def test_ned_interfaces_must_name_an_interface_unless_it_is_left_out(rest):
    with pytest.raises(ValueError, match="names no interface"):
        Neds(rest, ned_interfaces=[])


@pytest.mark.parametrize("ned_interfaces", [[2], (2,), {2}, frozenset({2}), iter([2]), range(2, 3)])
def test_any_collection_of_whole_numbers_names_the_interfaces(rest, ned_interfaces):
    assert Neds(rest, ned_interfaces=ned_interfaces).ned_interfaces == frozenset({2})


@respx.mock
def test_the_same_reason_is_logged_once(neds, caplog):
    list_on_the_api(published(interface_version=3))

    with caplog.at_level(logging.WARNING, logger="acex_client.neds"):
        neds.get_missing()
        neds.get_missing()

    assert [r.getMessage() for r in caplog.records] == [f"NED not used: {neds.incompatible['CiscoIOS']}"]


@respx.mock
def test_a_changed_reason_replaces_the_old_one_and_is_logged(neds, caplog):
    list_on_the_api(published(interface_version=3))
    with caplog.at_level(logging.WARNING, logger="acex_client.neds"):
        neds.get_missing()
        respx.reset()
        list_on_the_api(published(version="6.0.0", interface_version=4))
        neds.get_missing()

    assert neds.incompatible == {"CiscoIOS": reason(4, "2", "update this agent or worker", version="6.0.0")}
    assert [r.getMessage() for r in caplog.records] == [
        f"NED not used: {reason(3, '2', 'update this agent or worker')}",
        f"NED not used: {reason(4, '2', 'update this agent or worker', version='6.0.0')}",
    ]


@respx.mock
def test_a_reason_that_comes_back_after_it_was_fixed_is_logged_again(neds, caplog):
    with caplog.at_level(logging.WARNING, logger="acex_client.neds"):
        list_on_the_api(published(interface_version=3))
        neds.get_missing()
        respx.reset()
        list_on_the_api(published(interface_version=2))
        neds.get_missing()
        respx.reset()
        list_on_the_api(published(interface_version=3))
        neds.get_missing()

    assert len(caplog.records) == 2


@respx.mock
def test_install_refuses_before_anything_is_downloaded(neds):
    ned = Ned(**published(interface_version=3))

    with pytest.raises(AcexNedIncompatibleError, match="implements NED interface 3"):
        neds.install(ned)

    assert neds.incompatible == {"CiscoIOS": reason(3, "2", "update this agent or worker")}


def test_a_refusal_is_an_install_error_so_existing_handlers_catch_it():
    assert issubclass(AcexNedIncompatibleError, AcexNedInstallError)


@respx.mock
def test_load_refuses_a_driver_of_another_interface(neds):
    describe_on_the_api(published(interface_version=3))

    with pytest.raises(AcexNedIncompatibleError, match="update this agent or worker"):
        neds.load("CiscoIOS")

    assert "CiscoIOS" in neds.incompatible


@respx.mock
def test_load_hands_out_the_installed_driver_and_keeps_it_for_the_next_call(neds):
    describe_on_the_api(published(interface_version=2))

    with installed(_DriverOfInterface2), patch.object(Neds, "install") as install:
        first = neds.load("CiscoIOS")
        second = neds.load("CiscoIOS")

    assert isinstance(first, _DriverOfInterface2)
    assert second is first
    install.assert_not_called()


@respx.mock
def test_load_installs_the_driver_the_api_publishes_when_the_installed_one_is_another_version(neds):
    describe_on_the_api(published(version="6.0.0", interface_version=2))

    with installed(_DriverOfInterface2, version="5.0.0"), patch.object(Neds, "install", return_value=True) as install:
        neds.load("CiscoIOS")

    [(ned,), _] = install.call_args
    assert ned.version == "6.0.0"


@respx.mock
def test_load_refuses_an_installed_driver_the_process_cannot_run_and_does_not_keep_the_refusal(neds):
    describe_on_the_api(published(interface_version=2))

    with installed(_DriverOfInterface3), pytest.raises(AcexNedIncompatibleError, match="implements NED interface 3"):
        neds.load("CiscoIOS")

    with installed(_DriverOfInterface2):
        assert isinstance(neds.load("CiscoIOS"), _DriverOfInterface2)


@respx.mock
def test_load_says_why_the_installed_driver_cannot_be_loaded(neds):
    describe_on_the_api(published(interface_version=2))

    with installed(ImportError("No module named 'netmiko'")):
        with pytest.raises(AcexNedIncompatibleError, match="could not be loaded: ImportError: No module named"):
            neds.load("CiscoIOS")


def test_an_installed_driver_of_a_supported_interface_is_handed_out(neds):
    with installed(_DriverOfInterface2):
        assert isinstance(neds.get_driver_instance("CiscoIOS"), _DriverOfInterface2)


def test_an_installed_driver_of_another_interface_is_not_handed_out(neds):
    with installed(_DriverOfInterface3):
        assert neds.get_driver_instance("CiscoIOS") is None

    assert neds.incompatible == {"CiscoIOS": reason(3, "2", "update this agent or worker")}


def test_an_installed_driver_that_does_not_say_which_interface_is_handed_out(neds):
    with installed(_DriverThatDoesNotSay):
        assert isinstance(neds.get_driver_instance("CiscoIOS"), _DriverThatDoesNotSay)

    assert neds.incompatible == {}


def test_an_interface_that_is_not_a_plain_number_is_not_held_against_a_driver(neds):
    with installed(_DriverWithAProperty):
        assert isinstance(neds.get_driver_instance("CiscoIOS"), _DriverWithAProperty)


def test_a_process_that_names_no_interfaces_gets_every_installed_driver(rest):
    with installed(_DriverOfInterface3):
        assert isinstance(Neds(rest).get_driver_instance("CiscoIOS"), _DriverOfInterface3)


def test_an_installed_driver_that_cannot_be_imported_is_not_handed_out_and_does_not_stop_the_caller(neds, caplog):
    with caplog.at_level(logging.WARNING, logger="acex_client.neds"):
        with installed(ImportError("cannot import name 'TransportBase'")):
            assert neds.get_driver_instance("CiscoIOS") is None

    assert neds.incompatible == {
        "CiscoIOS": "CiscoIOS v5.0.0 could not be loaded: ImportError: cannot import name 'TransportBase'"
    }
    [record] = caplog.records
    assert record.exc_info[1].args == ("cannot import name 'TransportBase'",)


def test_an_installed_driver_that_cannot_be_built_is_not_handed_out_and_does_not_stop_the_caller(neds):
    with installed(_DriverThatCannotBeBuilt):
        assert neds.get_driver_instance("CiscoIOS") is None

    assert neds.incompatible == {"CiscoIOS": "CiscoIOS v5.0.0 could not be loaded: RuntimeError: no transport"}


def test_the_reason_about_the_installed_driver_goes_once_the_driver_loads(neds):
    with installed(_DriverOfInterface3):
        neds.get_driver_instance("CiscoIOS")
    assert neds.incompatible

    with installed(_DriverOfInterface2):
        assert neds.get_driver_instance("CiscoIOS") is not None

    assert neds.incompatible == {}


@respx.mock
def test_a_process_keeps_the_driver_it_has_when_the_api_publishes_a_newer_one_it_cannot_run(neds):
    list_on_the_api(published(version="6.0.0", interface_version=3))

    with installed(_DriverOfInterface2, version="5.0.0"):
        assert neds.get_missing() == []
        assert isinstance(neds.get_driver_instance("CiscoIOS"), _DriverOfInterface2)

    assert neds.incompatible == {"CiscoIOS": reason(3, "2", "update this agent or worker", version="6.0.0")}


@respx.mock
def test_what_is_wrong_with_the_installed_copy_comes_before_what_is_wrong_with_the_published_one(neds):
    list_on_the_api(published(version="6.0.0", interface_version=4))

    with installed(_DriverOfInterface3, version="5.0.0"):
        neds.get_missing()
        assert neds.get_driver_instance("CiscoIOS") is None

    assert neds.incompatible == {"CiscoIOS": reason(3, "2", "update this agent or worker", version="5.0.0")}


@respx.mock
def test_two_reasons_for_one_driver_are_each_logged_once_however_often_they_are_met(neds, caplog):
    list_on_the_api(published(version="6.0.0", interface_version=4))

    with caplog.at_level(logging.WARNING, logger="acex_client.neds"):
        for _ in range(3):
            with installed(_DriverOfInterface3, version="5.0.0"):
                neds.get_missing()
                neds.get_driver_instance("CiscoIOS")

    assert sorted(r.getMessage() for r in caplog.records) == sorted(
        [
            f"NED not used: {reason(4, '2', 'update this agent or worker', version='6.0.0')}",
            f"NED not used: {reason(3, '2', 'update this agent or worker', version='5.0.0')}",
        ]
    )
