"""The NED listing says which NED interface each driver implements, so a process can tell if it can run it."""

from __future__ import annotations

import pytest
from acex.plugins.neds.manager import ned_manager
from acex.plugins.neds.manager.ned_manager import NEDManager
from acex_devkit.drivers import NED_INTERFACE
from acex_devkit.models.ned import Ned


class _Dist:
    name = "acex-fake-ned"
    version = "1.2.3"


class _EntryPoint:
    value = "acex_fake_ned:FakeDriver"
    dist = _Dist()

    def __init__(self, load):
        self.load = load


class FakeDriver:
    """A driver on the current interface."""

    interface_version = NED_INTERFACE
    capabilities = None


class DriverThatDoesNotSay:
    capabilities = None


class DriverWithAProperty:
    capabilities = None

    @property
    def interface_version(self):
        return NED_INTERFACE


class DriverWithAFraction:
    capabilities = None
    interface_version = 2.5


class DriverWithABool:
    capabilities = None
    interface_version = True


def listing_of(monkeypatch, load) -> dict:
    monkeypatch.setattr(ned_manager, "entry_points", lambda group: [_EntryPoint(load)])
    [listed] = NEDManager().list_drivers()
    return listed


def test_a_listed_driver_carries_its_interface(monkeypatch):
    assert listing_of(monkeypatch, lambda: FakeDriver)["interface_version"] == NED_INTERFACE


def test_a_loaded_driver_carries_its_interface_in_its_info(monkeypatch):
    manager = NEDManager()
    manager.drivers["FakeDriver"] = {"instance": FakeDriver(), "version": "1.2.3", "package_name": "acex-fake-ned"}
    monkeypatch.setattr(manager, "_driver_filename", lambda name: "acex_fake_ned-1.2.3-py3-none-any.whl")
    monkeypatch.setattr(ned_manager, "entry_points", lambda group: [_EntryPoint(lambda: FakeDriver)])

    info = manager.get_driver_info("FakeDriver")
    [listed] = manager.list_drivers()

    assert info["interface_version"] == listed["interface_version"] == NED_INTERFACE
    assert Ned(**info).interface_version == NED_INTERFACE


def test_a_driver_that_does_not_say_is_listed_without_an_interface(monkeypatch):
    assert listing_of(monkeypatch, lambda: DriverThatDoesNotSay)["interface_version"] is None


def test_a_driver_that_cannot_be_loaded_is_listed_without_an_interface(monkeypatch):
    def broken():
        raise ImportError("its dependency is missing")

    assert listing_of(monkeypatch, broken)["interface_version"] is None


@pytest.mark.parametrize("interface", [1, NED_INTERFACE, 3])
def test_the_interface_of_a_driver_is_listed_as_it_is(monkeypatch, interface):
    driver_class = type("Driver", (FakeDriver,), {"interface_version": interface})

    assert listing_of(monkeypatch, lambda: driver_class)["interface_version"] == interface


@pytest.mark.parametrize("driver_class", [DriverWithAProperty, DriverWithAFraction, DriverWithABool])
def test_an_interface_that_is_not_a_plain_number_is_listed_as_not_said(monkeypatch, driver_class):
    listed = listing_of(monkeypatch, lambda: driver_class)

    assert listed["interface_version"] is None
    assert Ned(**{**listed, "description": "", "filename": "some.whl"}).interface_version is None


@pytest.mark.parametrize("driver_class", [DriverWithAProperty, DriverWithAFraction, DriverWithABool])
def test_one_driver_with_an_odd_interface_does_not_spoil_the_listing_of_the_others(monkeypatch, driver_class):
    manager = NEDManager()
    manager.drivers["Odd"] = {"instance": driver_class(), "version": "1.0.0", "package_name": "acex-fake-ned"}
    monkeypatch.setattr(manager, "_driver_filename", lambda name: "acex_fake_ned-1.0.0-py3-none-any.whl")
    odd_entry = _EntryPoint(lambda: driver_class)
    odd_entry.value = "acex_fake_ned:Odd"
    monkeypatch.setattr(ned_manager, "entry_points", lambda group: [_EntryPoint(lambda: FakeDriver), odd_entry])

    listed = manager.list_drivers()

    assert [entry["interface_version"] for entry in listed] == [NED_INTERFACE, None]
    assert manager.get_driver_info("Odd")["interface_version"] is None
    for entry in listed:
        Ned(**{**entry, "description": "", "filename": "some.whl"})
