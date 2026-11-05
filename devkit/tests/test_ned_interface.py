"""A driver says which NED interface it implements, and the NED listing carries it."""

from acex_devkit.drivers import NED_INTERFACE, NetworkElementDriver
from acex_devkit.models.ned import Ned

LISTED = {"name": "Some", "package_name": "some", "version": "1.0.0", "description": "", "filename": "some.whl"}


class SomeDriver(NetworkElementDriver):
    pass


def test_a_driver_implements_the_interface_devkit_defines():
    assert NetworkElementDriver.interface_version == NED_INTERFACE
    assert SomeDriver.interface_version == NED_INTERFACE


def test_a_listed_ned_carries_the_interface_when_it_is_known():
    assert Ned(**LISTED, interface_version=NED_INTERFACE).interface_version == NED_INTERFACE


def test_a_listed_ned_from_a_backend_that_does_not_say_is_still_valid():
    assert Ned(**LISTED).interface_version is None
    assert Ned.model_validate(LISTED).model_dump()["interface_version"] is None
