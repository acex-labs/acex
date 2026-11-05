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
