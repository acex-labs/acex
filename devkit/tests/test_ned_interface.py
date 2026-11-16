"""A driver says which NED interface it implements, and the NED listing carries it."""

from acex_devkit.drivers import NED_INTERFACE, NetworkElementDriver
from acex_devkit.models.ned import Ned

LISTED = {"name": "Some", "package_name": "some", "version": "1.0.0", "description": "", "filename": "some.whl"}


class SomeDriver(NetworkElementDriver):
    pass


class DeclaringDriver(NetworkElementDriver):
    interface_version = NED_INTERFACE


def test_devkit_defines_a_numbered_interface():
    assert type(NED_INTERFACE) is int
    assert NED_INTERFACE >= 1


def test_a_driver_does_not_inherit_the_interface_of_the_devkit_it_is_loaded_under():
    assert NetworkElementDriver.interface_version is None
    assert SomeDriver.interface_version is None


def test_a_driver_declares_its_interface_in_its_class_body():
    assert DeclaringDriver.interface_version == NED_INTERFACE
    assert vars(DeclaringDriver)["interface_version"] == NED_INTERFACE


def test_a_listed_ned_carries_the_interface_when_it_is_known():
    assert Ned(**LISTED, interface_version=NED_INTERFACE).interface_version == NED_INTERFACE


def test_a_listed_ned_from_a_backend_that_does_not_say_is_still_valid():
    assert Ned(**LISTED).interface_version is None
    assert Ned.model_validate(LISTED).model_dump()["interface_version"] is None
